# 澜語輸入法 LanType 1.1.0

LanType 是基於 CyIME 1.15.94 與 Rime 的獨立 GPLv3 Android 輸入法，支援中文與美式英文。適用 Android 9 以上 ARM64 裝置。應用程式不申請 `INTERNET` 權限；開發電腦可下載公開建置依賴。

本版加入「工具艙」：單位換算、明確讀取選取文字後進行遮罩及格式轉換，以及帶日期、時間和游標位置的動態範本。結果先預覽，再由使用者確認插入。剪貼簿範本另外確認讀取；密碼或受限制欄位無法使用這些工具。

本輪重新整理商業發行資源，使用 AOSP/rime-pinyin-simp、CC-CEDICT、SCOWL、Whisper、PP-OCRv5，以及由 MakeMeAHanzi 筆畫中線生成的單字手寫範本。手寫依正常筆順比對，不承諾連筆、草書或整行辨識；更換模型後的品質與速度須在目標裝置驗證。

應用程式可依 GPLv3 收費分發，接收者保有取得對應原始碼、修改與再分發的權利。模型、詞典及圖形資料各自保留原授權，不能以頂層 GPL 取代。應用程式沒有線上啟用機制。

完整文件請見 [主說明](README.md)、[安裝說明](docs/INSTALLATION.zh-CN.md)、[隱私說明](docs/PRIVACY.zh-CN.md)、[商用方案](docs/COMMERCIAL-PLAN.zh-CN.md)、[建置及原始碼來源](docs/LANTYPE-BUILD-AND-SOURCES.md) 與 [1.1.0 驗收記錄](docs/validation-1.1.0/VALIDATION.md)。隨包授權全文可以離線閱讀。本產品不是 CyIME 官方發行版。
