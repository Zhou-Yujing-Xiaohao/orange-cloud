#!/usr/bin/env python3
"""
prepare_ios_build.py
在 GitHub Actions 构建前运行：把 fork 的源码就地改造成"你自己的全功能自编译版"。
所有可变配置来自环境变量（由 GitHub Secrets 注入），不写死在代码里。

用法:
  BUNDLE_PREFIX=com.example.oc \
  TEAM_ID=YOURTEAMID \
  APP_GROUP=com.example.oc.group \
  CLIENT_ID=xxxx \
  REDIRECT_URI=https://xxx.workers.dev/oauth/callback \
  CALLBACK_SCHEME=orangecloud \
  python3 scripts/prepare_ios_build.py
"""
import os
import pathlib
import sys

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
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8")
    new = text
    for old, val in pairs:
        if val and old != val:
            new = new.replace(old, val)
    if new != text:
        path.write_text(new, encoding="utf-8")
        changes.append(str(path))

# 1) 全 iOS 目录：Bundle ID 前缀、App Group、Team ID
pairs_common = [
    (OLD_APP_GROUP, APP_GROUP),
    (OLD_BUNDLE_PREFIX, BUNDLE_PREFIX),
    (OLD_TEAM, TEAM_ID),
]
if ROOT.exists():
    for p in ROOT.rglob("*"):
        if p.is_file() and p.suffix in {".swift", ".plist", ".entitlements", ".pbxproj", ".xcscheme"}:
            replace_in_file(p, pairs_common)

# 2) OAuthConfig.swift：Client ID / Redirect URI / scheme
oauth = ROOT / "Orange Cloud/Core/Auth/OAuthConfig.swift"
replace_in_file(oauth, [
    (f'static let clientID = "{OLD_CLIENT_ID}"', f'static let clientID = "{CLIENT_ID}"'),
    (f'static let redirectURI = "{OLD_REDIRECT}"', f'static let redirectURI = "{REDIRECT_URI}"'),
    (f'static let callbackScheme = "{OLD_SCHEME}"', f'static let callbackScheme = "{CALLBACK_SCHEME}"'),
])

# 3) Info.plist 里的 URL scheme（若自定义）
info = ROOT / "Orange Cloud/Info.plist"
if CALLBACK_SCHEME:
    replace_in_file(info, [(OLD_SCHEME, CALLBACK_SCHEME)])

print("=== prepare_ios_build.py done ===")
print("Modified files:")
for c in sorted(set(changes)):
    print("  -", c)
if not changes:
    print("  (no changes — all env vars were empty)")

# 必填校验：解锁构建至少要有 Client ID / Redirect URI，否则装上了也登不进去
missing = []
if not CLIENT_ID:    missing.append("CLIENT_ID")
if not REDIRECT_URI: missing.append("REDIRECT_URI")
if missing:
    print("\n[WARN] Missing Secrets: " + ", ".join(missing) + " — 构建出的 App 将无法 OAuth 登录。")
    print("       请在仓库 Settings → Secrets and variables → Actions 中配置。")
