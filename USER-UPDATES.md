# 系統更新紀錄（用戶版）

俾用戶睇嘅更新公告，最新喺最上面，可以直接複製去 WhatsApp。技術細節見 [CHANGELOG.md](CHANGELOG.md)。

- **正式機**：<http://57.180.114.85>
- **測試機**：<http://3.114.114.143>（新功能會先喺度試用）

---

## 04/11/2026

### 【測試機】Inventory 倉庫同中心分開

<http://3.114.114.143/attendance/inventory/warehouses>

- 側欄 Inventory → Stock → **Warehouses**：可以新增、修改、停用倉庫
- 倉庫編號會用喺採購單、發票等單號（例如 `PO-MK-000001`）
- 可以揀呢個倉庫屬於邊個中心，也可以留空
- 已經有庫存或者單據嘅倉庫唔可以刪除，系統會提示改為停用
- 升級之後，之前用過嘅中心會自動變成同名倉庫，原有庫存同單據數量不變
- 庫存總覽、採購、銷售等頁面嘅選單改為 **Warehouse 倉庫**；如果未有倉庫，總覽會帶你去倉庫頁先開一個

### 【測試機】Inventory 各頁面統一介面、操作提示同修正

<http://3.114.114.143/attendance/inventory/items>

- **操作提示**：存檔、確認、作廢、收款、匯入 CSV 等成功後，畫面頂部會彈出提示（例如「Item B001G saved」「Receipt SR-… posted · HK$80.00」），唔再喺頁面頂部顯示一條會跟住滾動走嘅橫額
- **出錯提示**：喺彈出視窗入面操作出錯，錯誤會直接顯示喺視窗裏面（唔會再被視窗擋住）；喺頁面上操作出錯會彈出紅色提示
- **加品項提示**：喺採購單、銷售單、收貨單、退貨單加品項時，如果重複揀同一個品項，會自動合併數量並提示「Qty +1 for …」；停用品項會被拒絕並提示
- **彈出視窗**：全部改成分段（Identification / Lines / Payment…）、手機闊度會自動全螢幕、收貨單同退貨單加咗每行小計同總額
- **金額格式**：全部統一顯示成「HK$1,234.50」；日期時間統一用香港時間
- **空白頁面**：冇資料時會顯示圖示同「新增」按鈕；Items 同 Stock 搜尋可以用 barcode
- **今次修正**：
  - 「New Invoice」一打開就出錯、揀銷售單顯示 undefined —— 已修好（由銷售單頁跳過嚟都會預選銷售單）
  - 收款「Paid by」下拉顯示 [object Object] —— 已修好
  - 有整單折扣嘅發票而家可以全數開折讓單；已全數收款嘅發票要先作廢收據先開到折讓單（掣會灰色並提示）
  - 盤點「Apply」改為按差異調整：盤點期間發生嘅出入貨唔會被覆蓋
  - 取消銷售單會連同草稿發票一齊刪除；已取消銷售單嘅發票唔能再開立

### 【測試機】Inventory 商品可以加 Barcode 同其他成本

<http://3.114.114.143/attendance/inventory/items>

- 新增／編輯商品多咗兩格：**Barcode**（條碼，可以掃或者手打，選填）同 **Other cost**（其他成本，選填）
- 之前嗰格「Cost price」改名做 **Purchase price**，意思一樣，入咗嘅資料唔受影響
- Items 表格而家會顯示 **Purchase price** 同 **Other cost** 兩欄（之前嘅「Cost」欄改名做「Purchase price」）
- CSV 滙出／滙入多咗 `barcode` 同 `other_cost` 兩欄；舊格式嘅 CSV 繼續用得

## 29/10/2026

### 【測試機】手機 App 可以用員工編號 + PIN 登入幫人簽到

- 員工而家可以用 **員工編號 + 6 位 PIN**（同報更用嘅係同一個 PIN）登入手機 App
- 登入之後撳 **掃描** 分頁，揀簽到／簽退同地點，就可以掃學生或者其他員工嘅 QR 幫佢哋打卡
- **紀錄** 分頁會見到今日由你掃嘅所有打卡
- 所有員工**預設都有呢個權限**；如果想取消某個員工嘅掃碼權限，Admin 可以去員工資料取消勾選「Can take attendance」
- 員工只能喺自己返開嘅分店掃碼，冇得改或者作廢紀錄（要改請搵 Admin）
- **要裝新版 App 先用得**

### 【測試機】名冊「Join a student」可以直接幫在讀學生加堂／改日期

<http://3.114.114.143/attendance/courses>

- 班次名冊「Join a student」：揀咗已經喺班嘅學生，唔會再顯示「already in the class」鎖住個掣
- **堂費班**：個掣變「Top up sessions」，填加幾多堂（同埋新嘅結束日，如果要延長），撳落去就會加多一筆買堂紀錄，之前嘅紀錄會保留，每筆分開出單
- **月費班**：個掣變「Update」，會自動填返而家嘅開始／結束日同價錢，改完撳落去就更新
- 表格嗰個 **Edit** 照用得；堂費班撳 **Edit** 會見到「Purchase history」，列晒每次買堂嘅日期、堂數、價錢同出咗單未
- 撳表格「Sessions」嗰格（例如「37 sessions ⌄」），下面會展開每次買堂紀錄，再撳一次收埋
- 加堂時開始日唔可以早過學生原本嘅開始日；表單下面會講明結束日會延長定唔變
- 如果同一日已經加過一樣堂數，會再問一次，避免重複撳

## 27/10/2026

### 【正式機】收據列印顯示中心 Logo

<http://57.180.114.85/attendance/receipts>

- 列印 **Official Receipt** 時，左上角會顯示返中心 Logo（之前有時會印咗空白）
- Logo 用中心嘅 **Icon**；未設定 Icon 就用 **Main photo**
- 想更改 Logo：去 **Location Management** → 編輯中心 → **Photos**

### 【正式機】確認視窗加咗提示圖示

- 刪除、作廢等確認視窗，標題左邊會多一個圖示：紅色代表**刪除／作廢等唔可以還原**嘅操作
- 操作方法同之前一樣，冇其他改動

### 【測試機】新功能：Inventory 庫存管理（試用）

<http://3.114.114.143/attendance/inventory/workflow>

測試機側欄新增 **Inventory**，用嚟管理貨品、入貨同銷售。正式機暫時未開放。

- **Start Here**：有成個流程圖，第一次用建議先睇
- **Stock**：建立貨品（**Items**）、睇各中心庫存、盤點（**Stocktakes**）、查異動紀錄（**Movements**）
- **Buying**：開採購單（**Purchase Order**）→ 收貨（**Goods Receipt**）→ 有需要可退貨（**Purchase Return**）
- **Selling**：開銷售單（**Sales Order**，可列印報價單 Proforma）→ 開發票（**Sales Invoice**）→ 送貨（**Delivery Order**）→ 收款（**Sales Receipt**）；退款用 **Sales Credit Note**
- **開發票嗰陣就會扣庫存**，唔係送貨先扣
- **Reports / Dashboard**：銷售、庫存同每月數字
- 庫存低於「Reorder level」、採購單過期、發票逾期未收款，系統會發通知俾管理員
- Inventory 嘅發票、收據、編號同學費完全分開，**唔會影響**學費發票、收據同糧單

### 【測試機】貨品可以上載 3 張相

<http://3.114.114.143/attendance/inventory/items>

- 每件貨品可以上載 **1 張主圖（Main image）+ 2 張副圖（Sub image 1 / 2）**
- 貨品列表只會顯示主圖
- 上載相片後要撳 **Save** 先會儲存；撳 Cancel 唔會保存

---

## 12/10/2026

### 【正式機】導師佣金功能更新

<http://57.180.114.85/attendance/units>

系統現已支援自動計算導師佣金，主要更新如下：

- 可於導師資料嘅 **Compensation** 部分開啟 **Commission / sharing**
- 開啟後預設佣金比例為 **70%**，亦可自行設定 **0%–100%**
- 建立發票時，請選擇正確嘅 **Tutor**
- 佣金會按**已收款發票總額 × 佣金比例**自動計算
- 佣金會計入實際**收款月份**；例如 10 月發票喺 11 月收款，佣金會計入 11 月糧單
- 如有已發出或已付款嘅 **Credit Note**，相關金額會自動扣減
- 計算後嘅佣金會獨立顯示喺糧單嘅 **Commission** 一行，並計入 Gross pay；**Adjustment 1 / 2** 繼續保留作人工調整
- 即使導師當月冇考勤紀錄，只要有合資格嘅已收款發票，系統仍會建立糧單
- 未付款、草稿、已作廢嘅發票，以及已作廢嘅 Receipt，均唔會計算佣金
- 可於糧單 **Details → Commission** 查看已計算發票、Credit Note 同等待付款嘅發票
- 已經 **Approved** 或 **Paid** 嘅糧單唔會被重新計算或覆蓋

#### 使用方法

1. 建立發票時選擇正確嘅 **Tutor**
2. 收款後使用 **Mark Paid** 建立並確認 Receipt
3. 前往 Payroll，Generate 收款日期所屬月份嘅糧單
4. 系統會自動計算佣金並顯示喺 **Commission** 一行

**溫馨提示：**
**Save & Print** 只會儲存及列印發票，唔代表已經收款。必須完成 **Mark Paid／Receipt** 流程後，相關發票先會計算佣金。如 Commission 顯示 `$0.00`，可到 **Details → Commission** 查看係咪仲有發票等待付款。
