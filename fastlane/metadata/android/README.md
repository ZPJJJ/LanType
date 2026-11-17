# LanType 商店文案草稿

这些文件描述 LanType 1.1.0 的实际离线能力，不表示已提交或通过任何商店审核。应用标题、说明和图标均使用独立品牌。完整商用安排见 [商用方案](../../../docs/COMMERCIAL-PLAN.zh-CN.md)。

图标由当前 Android 矢量资源 `lantype_mark.xml` 原样导出为 512×512 PNG；可编辑矢量源保存在 `docs/branding/lantype-icon.svg`。不沿用上游 Xime 或 CyIME 商店图标。此目录未放入冒充真机的界面截图，手机商店截图需完成实际设备验证后制作。

可从仓库根目录用 Inkscape 重新导出：

```sh
inkscape docs/branding/lantype-icon.svg --export-type=png --export-filename=fastlane/metadata/android/zh-CN/images/icon.png --export-width=512 --export-height=512
```

发布前还需填写真实销售主体、联系邮箱、隐私政策公开地址、价格、支持/退款规则和渠道数据安全表，完成目标设备测试及相应商店审核。源码、资源许可、原生对应源码及校验值必须与实际版本配套发布。
