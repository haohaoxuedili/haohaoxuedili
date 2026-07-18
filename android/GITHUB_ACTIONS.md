# 通过 GitHub Actions 云端编译 Android APK

无需在本机装 WSL / Docker / 管理员权限，完全在云端完成。

## 一次性准备

### 1. 注册 GitHub 账号 (如已有可跳过)
https://github.com/signup

### 2. 创建一个新仓库
- 浏览器打开 https://github.com/new
- Repository name: `ncm2mp3` (任意)
- 选 **Private** (私有仓库，避免源码公开)
- **不要**勾选 "Add README" / ".gitignore" / "License" (本地已有)
- 点 Create repository

## 推送代码到 GitHub

在项目目录 `D:\我的文件\idoknow\Haohaoxuedili` 下用 PowerShell：

```powershell
# 初始化 git (如果还没初始化)
git init
git branch -M main

# 添加远程仓库 (把 <你的名字> 改成你的 GitHub 用户名)
git remote add origin https://github.com/<你的名字>/ncm2mp3.git

# 首次推送
git add .
git commit -m "init: NCM to MP3/FLAC converter (PC + Android)"
git push -u origin main
```

第一次推时会弹窗要登录 GitHub：用浏览器认证即可。

## 触发 Actions 自动编译

推完后，浏览器进入仓库页面：

1. 点顶部 **Actions** 标签
2. 左侧选 **Build Android APK**
3. 右侧点 **Run workflow** → 选 `main` 分支 → 绿色 Run workflow 按钮

就在云端开始编译了。首次大约 30-45 分钟（GitHub 服务器也要下载 Android SDK/NDK 等）。

## 下载 APK

1. 编译完成后，回到 **Actions** 标签
2. 点最新一次成功的运行 (带绿勾)
3. 拉到底部 **Artifacts** 区，点 `ncm2mp3-apk` 下载
4. 解压得到 `ncm2mp3-1.0.0-debug.apk`

## 在手机上安装

1. 把 apk 传到手机 (微信/QQ / 网盘 / USB)
2. 手机设置 → 安全 → 允许"未知来源应用安装"
3. 文件管理器点击 apk → 安装
4. 打开 App，授予存储权限
5. 点 "+ 添加 NCM 文件" → 选 `.ncm` → 开始转换
6. 输出目录: `/sdcard/NCM2MP3_Output/`

## 后续更新

每次修改了 `android/` 目录或 `.github/workflows/build-apk.yml` 推送后，Actions 会自动重新编译；
也可手动在 Actions 页面点 **Run workflow** 触发。

## 常见问题

| 现象 | 原因 | 解决 |
|---|---|---|
| Actions 没开始 | 私有仓库免费账号每月 2000 分钟免费额度，超出要付费 | 公开仓库无限免费，如不在乎源码公开可改 Public |
| 提示 Cython 编译失败 | 偶发，重建一次即可 | Actions 页面点 Re-run |
| 推送时认证失败 | 凭据过期 | 控制面板 → 凭据管理器 → Windows 凭据 → 删除 github.com 相关条目，再推一次重新登录 |
| APK 启动闪退 | 多半权限被拒 | adb logcat 看堆栈；或在 Settings 给 App 全部文件访问权限 |

## 改用其它 CI (可选)

如不想用 GitHub，相同思路可用：
- GitLab CI (自带 Android 模板)
- 自己有 Linux 服务器 → SSH 进去执行 `buildozer -v android debug`
