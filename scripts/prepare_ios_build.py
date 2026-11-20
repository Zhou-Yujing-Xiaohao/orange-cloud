#!/usr/bin/env python3
"""
prepare_ios_build.py
在 GitHub Actions 构建前运行：把 fork 的源码就地改造成"你自己的全功能自编译版"。
所有可变配置来自环境变量（由 GitHub Secrets / Variables 注入），不写死在代码里。
只在注入值非空时才替换，未提供的项保留原值。

用法:
  BUNDLE_PREFIX=com.example.oc \
  TEAM_ID=YOURTEAMID \
  APP_GROUP=group.com.example.oc \
  CLIENT_ID=xxxx \
  REDIRECT_URI=https://xxx.workers.dev/oauth/callback \
  CALLBACK_SCHEME=orangecloud \
  python3 scripts/prepare_ios_build.py
"""
import os
import pathlib

ROOT = pathlib.Path("apps/ios/Orange Cloud")

# ---- 从环境变量读取（全部可选；留空则保留原值）----
BUNDLE_PREFIX   = os.environ.get("BUNDLE_PREFIX", "").strip()   # 例: com.example.oc
TEAM_ID         = os.environ.get("TEAM_ID", "").strip()         # 例: ABCDE12345
APP_GROUP       = os.environ.get("APP_GROUP", "").strip()       # 例: group.com.example.oc
CLIENT_ID       = os.environ.get("CLIENT_ID", "").strip()
REDIRECT_URI    = os.environ.get("REDIRECT_URI", "").strip()
CALLBACK_SCHEME = os.environ.get("CALLBACK_SCHEME", "").strip()

OLD_BUNDLE_PREFIX = "jiamin.chen.orange-cloud"
OLD_APP_GROUP     = "group.jiamin.chen.Orange-Cloud"
OLD_TEAM          = "6G78MMY657"
OLD_CLIENT_ID     = "102240eb9095a1965ee11813ef4788cd"
OLD_REDIRECT      = "https://o-c.do/oauth/callback"
OLD_SCHEME        = "orangecloud"

changes = []

def replace_in_file(path: pathlib.Path, pairs):
    """pairs: 已过滤好的 (old, new) 列表，逐项替换。"""
    if not path.exists() or not pairs:
        return
    text = path.read_text(encoding="utf-8")
    new = text
    for old, val in pairs:
        new = new.replace(old, val)
    if new != text:
        path.write_text(new, encoding="utf-8")
        changes.append(str(path))

# 1) 全 iOS 目录：Bundle ID 前缀、App Group、Team ID（仅在注入值非空时替换）
pairs_common = []
if APP_GROUP:     pairs_common.append((OLD_APP_GROUP, APP_GROUP))
if BUNDLE_PREFIX: pairs_common.append((OLD_BUNDLE_PREFIX, BUNDLE_PREFIX))
if TEAM_ID:       pairs_common.append((OLD_TEAM, TEAM_ID))

if ROOT.exists():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in {".swift", ".plist", ".entitlements", ".pbxproj", ".xcscheme"}:
            replace_in_file(p, pairs_common)

# 2) OAuthConfig.swift：Client ID / Redirect URI / scheme（仅在注入值非空时替换）
oauth_pairs = []
if CLIENT_ID:    oauth_pairs.append((f'static let clientID = "{OLD_CLIENT_ID}"',    f'static let clientID = "{CLIENT_ID}"'))
if REDIRECT_URI: oauth_pairs.append((f'static let redirectURI = "{OLD_REDIRECT}"', f'static let redirectURI = "{REDIRECT_URI}"'))
if CALLBACK_SCHEME: oauth_pairs.append((f'static let callbackScheme = "{OLD_SCHEME}"', f'static let callbackScheme = "{CALLBACK_SCHEME}"'))
replace_in_file(ROOT / "Orange Cloud/Core/Auth/OAuthConfig.swift", oauth_pairs)

# 3) Info.plist 里的 URL scheme（仅在自定义时替换）
if CALLBACK_SCHEME and CALLBACK_SCHEME != OLD_SCHEME:
    replace_in_file(ROOT / "Orange Cloud/Info.plist", [(OLD_SCHEME, CALLBACK_SCHEME)])

print("=== prepare_ios_build.py done ===")
if changes:
    print("Modified files:")
    for c in sorted(set(changes)):
        print("  -", c)
else:
    print("No changes (all injected values were empty).")

# 必填校验：解锁构建至少要有 Client ID / Redirect URI，否则装上了也登不进去
missing = []
if not CLIENT_ID:    missing.append("CF_CLIENT_ID")
if not REDIRECT_URI: missing.append("CF_REDIRECT_URI")
if missing:
    print("\n[WARN] Missing Secrets: " + ", ".join(missing) + " — 构建出的 App 将无法 OAuth 登录。")
    print("       请在仓库 Settings → Secrets and variables → Actions 中配置。")
