# 系統更新紀錄（用戶版）

俾用戶睇嘅更新公告，最新喺最上面，可以直接複製去 WhatsApp。技術細節見 [CHANGELOG.md](CHANGELOG.md)。

- **正式機**：<http://57.180.114.85>
- **測試機**：<http://3.114.114.143>（新功能會先喺度試用）

---

## 12/11/2026

### 【測試機】中文名唔再必填、地點卡片同單據金額

<http://3.114.114.143/attendance/inventory/items>

- 倉庫、品牌、分類、貨品、供應商、客戶新增時，**中文名唔再必填**，填英文名都得（中英文最少填一個）；淨係填英文名嘅話，系統會用英文名當中文名顯示
- 地點卡片嘅 logo 背景改為白色，睇得清楚啲
- 採購單、銷售單、發票等單據入面嘅金額唔會再斷行

## 10/11/2026

### 【測試機】收貨單可以改日期同備註

<http://3.114.114.143/attendance/inventory/goods-receipts>

- 補舊單填錯收貨日期？**Draft** 收貨單撳右上角 **⋮ → Edit date & notes**，改完撳 **Save** 就得
- 收貨單詳情而家會顯示備註
- 補舊收貨單 Confirm 之後，庫存異動紀錄會顯示實際收貨日期，報表亦會跟實際日期計
- 新增收貨單時，Receipt date 下面有提示：補舊單請填實際收貨日期
- 已經 Confirm 咗嘅收貨單唔可以直接改；日期錯咗就 **Void** 再重新開過一張

### 【測試機】Inventory 貨品頁改版：New item、多個規格、Categories & Brands

<http://3.114.114.143/attendance/inventory/items>

<http://3.114.114.143/attendance/inventory/categories>

- 貨品頁改成「一行一件貨」；有多個規格嘅貨品可以撳左邊箭咀展開，睇到每個規格（Variant）嘅 Sale price、Cost price、Barcode 同 Stock
- 右上角撳 **New item**：填 Name、Code、Brand、Category，就可以儲存一件單品
- 如果貨品有多個規格（例如校服 T-shirt 有 S／M／L／XL），打開 **「This item has variants」**，填 Option name 同 Values（例如 Size：S, M, L, XL），下面會自動出一行行嘅表格，喺表格直接填每個規格嘅價錢、條碼同 Reorder level，最後撳 **Save** 一次過搞掂
- 表格上面有 **Apply to all**，價錢相同嘅規格可以一次填晒
- 之後想加新規格（例如 XXL），打開呢件貨再加 Values，新嘅規格會標示「New」；已經有庫存紀錄嘅選項唔可以刪除，但可以喺表格停用
- 如果將整件貨停用（Active 關閉），佢所有規格會一齊停用
- **Categories & Brands** 有獨立頁面（右上角 Categories & Brands 按鈕）：分類最多兩層（例如：家用電器 › 智能手機），Brand（例如 IKEA）係獨立欄位，兩者可以自由配搭；New item 時都可以按旁邊嘅 ＋ 即時新增
- 貨品頁可以按名稱／編號／條碼、Brand、Category 篩選；揀上層分類會包括佢下面嘅子分類
- CSV 匯入／匯出（右上角 CSV 掣）多咗 brand 欄，子分類會寫成「上層 > 子分類」；暫時 CSV 未有多規格資料
- 已經有嘅單品唔受影響；單品暫時唔可以改做多規格
- 新增貨品揀規格時，會列出其他貨品用過嘅規格同選項（例如 Size：S、M、L、XL），可以直接揀或者按「Add all」，亦可以輸入新嘅
- Start Here 頁已更新（<http://3.114.114.143/attendance/inventory/workflow>）：中英對照、新增「貨品與規格」說明圖（可下載）、「維護貨品」步驟同 FAQ 常見問題

## 05/11/2026

### 【測試機】Inventory 開始頁改為倉庫步驟

<http://3.114.114.143/attendance/inventory/workflow>

- **Start Here** 先教開倉庫、建品項、登記期初數量
- 進貨要 Confirm 收貨單先加庫存；賣貨開立發票先扣庫存。出貨單只記錄送貨
- Quick Fulfill 可以同時開出貨單和收據，也可以之後再補
- 盤點、調撥、報表的字眼由「分校」改為「倉庫」

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
