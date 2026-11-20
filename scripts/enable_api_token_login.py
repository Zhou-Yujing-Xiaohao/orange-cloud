#!/usr/bin/env python3
"""
enable_api_token_login.py
在 fork 源码上启用「直接粘贴 Cloudflare API Token 登录」，绕开自建 OAuth Client + 回调中转。

改动：
  1) AuthManager.swift：在 `// MARK: - 登录（新增身份）` 之前注入 loginWithAPIToken(_:) 方法
     - 用 /user/tokens/verify 验证 token 有效性
     - 包装成"永不过期"的 StoredToken（expiresAt = 100 年后、refreshToken = nil）
       → CFAPIClient 的临期刷新逻辑（expiresAt < 60s 才刷新）永不触发，长期 token 不会被误刷新
     - scope 设为全部已知权限，避免 UI 的功能门控误伤
  2) LoginView.swift：在 OAuth 登录 NavigationLink 之后插入 API Token 入口 NavigationLink
  3) 写入 ApiTokenLoginView.swift 到 Views/Auth/

用法（仓库根目录）：
  python3 scripts/enable_api_token_login.py
幂等：重复运行不会重复插入。
"""
import pathlib
import sys

ROOT = pathlib.Path("apps/ios/Orange Cloud/Orange Cloud")

AUTH = ROOT / "Core/Auth/AuthManager.swift"
LOGIN = ROOT / "Views/Auth/LoginView.swift"
NEWVIEW = ROOT / "Views/Auth/ApiTokenLoginView.swift"

# ---------- 1) 注入 AuthManager 方法 ----------
METHOD = '''
    // MARK: - API Token 直登（自建补丁；长期 token，无需 OAuth 刷新）
    /// 用手动创建的 Cloudflare API Token 登录：先调用 /user/tokens/verify 验证，
    /// 再包装成永不过期的 StoredToken 存入 Keychain。expiresAt 设为 100 年后，
    /// CFAPIClient 的临期刷新（<60s）与 401 refresh 都不会误伤长期 token。
    func loginWithAPIToken(_ rawToken: String) async {
        isLoading = true
        errorMessage = nil
        defer { isLoading = false }
        let token = rawToken.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !token.isEmpty else { errorMessage = "Token 不能为空"; return }

        // 1. 验证 token：GET /user/tokens/verify，Bearer token
        do {
            var req = URLRequest(url: URL(string: "https://api.cloudflare.com/client/v4/user/tokens/verify")!)
            req.setValue("Bearer \\(token)", forHTTPHeaderField: "Authorization")
            let (data, resp) = try await URLSession.shared.data(for: req)
            guard (resp as? HTTPURLResponse)?.statusCode == 200 else {
                errorMessage = "Token 验证失败，请检查是否复制完整、权限是否正确"
                return
            }
            // 解析 CF 响应，确认 result.status == "active"
            struct VerifyResult: Decodable { let status: String }
            struct VerifyResp: Decodable { let success: Bool; let result: VerifyResult? }
            let decoded = try? JSONDecoder().decode(VerifyResp.self, from: data)
            guard decoded?.success == true, decoded?.result?.status == "active" else {
                errorMessage = "Token 无效或已被吊销"
                return
            }
        } catch {
            errorMessage = "验证失败：\\(error.localizedDescription)"
            return
        }

        // 2. 包装成"永不过期"token。scopes 填全部 Cloudflare OAuth scope，
        //    确保 hasScope(_:) 的功能门控全部放行（API Token 本身权限由 Dashboard 决定）。
        let allScopes = [
            "account:read", "account:write", "zone:read", "zone:write",
            "zone_settings:read", "zone_settings:write", "dns:read", "dns:write",
            "cache_purge:write", "workers:read", "workers:write",
            "workers_kv:read", "workers_kv:write", "r2:read", "r2:write",
            "d1:read", "d1:write", "waf:read", "waf:write",
            "tunnel:read", "tunnel:write", "analytics:read", "user:read", "offline_access"
        ]
        let stored = TokenStore.StoredToken(
            accessToken: token,
            refreshToken: nil,
            expiresAt: Date().addingTimeInterval(100 * 365 * 24 * 3600),
            scope: allScopes.joined(separator: " ")
        )
        let id = UUID()
        TokenStore.save(stored, sessionId: id)
        AuthDiagnostics.recordWrite(refreshToken: nil, sessionId: id)
        let label = await fetchIdentityLabel(accessToken: token) ?? "API Token 账号"
        sessions.append(AuthSessionMeta(id: id, label: label, scopes: allScopes))
        currentSessionId = id
        persist()
        AppLog.auth.notice("api-token login stored session=\\(id.uuidString)")
    }

'''

MARKER = "    // MARK: - 登录（新增身份）"

def inject_method():
    text = AUTH.read_text(encoding="utf-8")
    if "func loginWithAPIToken" in text:
        print("  AuthManager: 已存在，跳过")
        return
    if MARKER not in text:
        print("  [ERROR] AuthManager 中找不到 marker:", MARKER, file=sys.stderr)
        sys.exit(2)
    text = text.replace(MARKER, METHOD + MARKER, 1)
    AUTH.write_text(text, encoding="utf-8")
    print("  AuthManager: 注入 loginWithAPIToken ✓")

# ---------- 2) LoginView 插入入口按钮 ----------
# 锚点：OAuth 登录按钮 NavigationLink 块结束后的 "// 免登录入口" 注释
ANCHOR = '        // 免登录入口：开发者工具箱（不依赖 CF 账号，作为拓客入口）'
BUTTON = '''        // API Token 直登入（自建补丁）
        NavigationLink {
            ApiTokenLoginView()
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "key.fill")
                Text("使用 API Token 登录（免 OAuth）")
                    .fontWeight(.medium)
            }
            .font(.body)
            .foregroundStyle(Color.ocOrangeText)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 14)
            .background(.regularMaterial, in: Capsule())
            .overlay(
                Capsule().strokeBorder(Color.ocOrange.opacity(0.35), lineWidth: 0.5)
            )
        }

'''

def inject_button():
    text = LOGIN.read_text(encoding="utf-8")
    if "ApiTokenLoginView()" in text:
        print("  LoginView: 已存在，跳过")
        return
    if ANCHOR not in text:
        print("  [ERROR] LoginView 中找不到 anchor", file=sys.stderr)
        sys.exit(3)
    text = text.replace(ANCHOR, BUTTON + ANCHOR, 1)
    LOGIN.write_text(text, encoding="utf-8")
    print("  LoginView: 插入 API Token 入口按钮 ✓")

# ---------- 3) 写入新视图文件 ----------
def write_view():
    src = pathlib.Path(__file__).parent / "ApiTokenLoginView.swift"
    if not src.exists():
        print("  [ERROR] 找不到 ApiTokenLoginView.swift（应与本脚本同目录）", file=sys.stderr)
        sys.exit(4)
    NEWVIEW.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    print("  ApiTokenLoginView.swift: 写入 ✓")

print("=== enable_api_token_login.py ===")
inject_method()
inject_button()
write_view()
print("完成。")
