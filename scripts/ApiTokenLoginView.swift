//  ApiTokenLoginView.swift
//  Orange Cloud — 自建补丁：用 Cloudflare API Token 直接登录（免 OAuth / 免回调中转）
//
//  用法：在 LoginView 的按钮区加一个 NavigationLink 指向本视图。
//  依赖 AuthManager 内部注入方法 loginWithAPIToken(_:)（由 prepare_token_login.py 注入）。

import SwiftUI

struct ApiTokenLoginView: View {
    @Environment(AuthManager.self) private var auth
    @Environment(\.dismiss) private var dismiss

    @State private var token = ""
    @State private var isValidating = false
    @State private var message = ""

    var body: some View {
        Form {
            Section {
                SecureField("粘贴 Cloudflare API Token", text: $token)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                Text("在 Cloudflare Dashboard → My Profile → API Tokens 创建。需要 Account 相关权限（如 Account:Settings:Read、Zone:DNS:Edit 等，按你要用的功能勾选）。")
                    .font(.footnote)
                    .foregroundStyle(.secondary)
            } header: {
                Text("API Token")
            }

            if !message.isEmpty {
                Section {
                    Text(message).foregroundStyle(.red).font(.footnote)
                }
            }

            Section {
                Button {
                    Task { await login() }
                } label: {
                    HStack {
                        if isValidating { ProgressView() }
                        Text("验证并登录")
                    }
                    .frame(maxWidth: .infinity)
                }
                .disabled(token.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || isValidating)
            } footer: {
                Text("Token 仅保存在本机钥匙串，不上传任何第三方服务器。长期有效，无需刷新。")
            }
        }
        .navigationTitle("使用 API Token 登录")
        .navigationBarTitleDisplayMode(.inline)
    }

    private func login() async {
        isValidating = true
        message = ""
        defer { isValidating = false }
        let trimmed = token.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else {
            message = "Token 不能为空"
            return
        }
        await auth.loginWithAPIToken(trimmed)
        if let err = auth.errorMessage, !err.isEmpty {
            message = err
        } else {
            dismiss()
        }
    }
}

#Preview {
    NavigationStack { ApiTokenLoginView().environment(AuthManager()) }
}
