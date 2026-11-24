# 系統更新紀錄（用戶版）

俾用戶睇嘅更新公告，最新喺最上面，可以直接複製去 WhatsApp。技術細節見 [CHANGELOG.md](CHANGELOG.md)。

- **正式機**：<http://57.180.114.85>
- **測試機**：<http://3.114.114.143>（新功能會先喺度試用）

---

## 24/11/2026

### 【測試機】admin 可以管理自己 Team 的 user 帳號

<http://3.114.114.143/attendance/users>

- admin 可以為自己的 Team 開 user 帳號，以及改資料、改密碼、停用登入
- 不能開 admin 或 superadmin，不能刪帳號。刪帳號仍然要 superadmin
- 這個 user 如果還屬於其他 Team，那些指派會保留
- admin 可以刪除自己 Team 的薪資紀錄。其他 Team 的薪資刪不到
- user 登入後可以進入客戶、QR、出席、服務、發票、收據和 Team。薪資、更表、員工管理和帳號頁仍然進不到
- 服務頁的 line item 清單不再因為舊的上課日格式而整頁失敗
- 每個 Team 的 line item 編號改回原本的編號，不再在後面加上 Team 編號

## 23/11/2026

### 【測試機】畫面用字

<http://3.114.114.143/attendance/users>

- 角色名稱是 superadmin、admin、user。補習社同 CPA 都係呢三個名
- 未指派時，CPA 顯示「未指派 Team，請聯絡 superadmin」；補習社顯示「未指派地點，請聯絡 superadmin」。可以登入，但未指派前看不到資料
- 提示跟品牌：補習社寫地點、學生；CPA 寫 Team、Client
- CPA 加發票 Job 會問「for this team」，只加入這個 Team。補習社的月份欄不變
- 加服務時會寫明只屬於所選的地點（CPA 顯示 Team）。新 Team 由空白開始
- 更表只會見到被指派的地點（CPA 顯示 Team）

### 【測試機】帳號要先指派 Team

<http://3.114.114.143/attendance/users>

- superadmin 在 User Management 開帳號，並揀這個帳號可以看哪些 Team
- admin 可以處理自己 Team 的客戶、出席、發票、收據、服務、更表和薪資，也可以刪自己 Team 的薪資紀錄。不能看 Audit Logs、不能刪 Team。開 user 帳號見 24/11/2026
- user 可以處理自己 Team 的客戶、出席、QR、發票、收據（包括作廢和刪除）。看不到薪資、時薪和分成，也沒有更表管理
- 服務、發票 Job、更表模板改成每個 Team 各有一份。舊資料已複製到每一個現有 Team。新 Team 由空白開始
- 手機 PIN 登入不變，仍然只看自己的更

### 【測試機】年費、收據版面、發票 JOB

<http://3.114.114.143/attendance/courses>

- 服務可以揀年費。有開始日期就每年在那一個月出一次；沒有開始日期就在 1 月出
- CPA 開發票時，每一行的 Period 改叫 Job。選已有項目就直接用。打新名稱時，該行會問要不要加入這個 Team 的清單，確認後這個 Team 才看得到。刪除項目會再問一次，只影響這個 Team。補習社的月份欄不變
- 服務揀了年費之後，價錢下面會寫明每年出一次，在開始的那一個月（沒有開始日期就在 1 月）
- 收據列印跟借項通知單同一種版面
- 側欄的 Inventory 先收起，之後會拿掉
- 正式機的月費、堂費、收據和月份欄不變

## 20/11/2026

### 【測試機】Team 聯絡人可以寫五行

<http://3.114.114.143/attendance/locations>

- 新增或編輯 Team，Contact 分頁的 Contact Person 變成 5 行，可以分行寫多過一個聯絡人
- 正式機的地點聯絡人仍然是一行

## 18/11/2026

### 【測試機】CPA 發票加 Remark、幣種同列印版本

<http://3.114.114.143/attendance/invoices>

- 開發票／改發票有兩個備註：Remark 1 印喺 DEBIT NOTE 標題下面，Remark 2 印喺明細表下面，冇填就唔印
- 發票可以揀幣種：HKD、USD、CNY、EUR、GBP、SGD、JPY，列印、發票列表、收條都會跟返嗰張單嘅幣種
- 列印金額係 0 嘅項目同總額會顯示 `-`
- 列印前會問用邊個版本：Version 1 Full（描述同金額）、Version 2（描述、單價、數量同金額）
- 發票列表上面嘅金額合計會按幣種分開顯示，例如 HK$9,000.00 · US$500.00
- 一張收條只可以收同一個幣種嘅發票，揀咗唔同幣種會提示，要分開開收條
- 員工分成只按 HKD 發票計入出糧；其他幣種嘅分成會另外列出（例如 Commission (USD)），唔會加入總薪金，薪資單都會列出
- 正式機唔變

## 17/11/2026

### 【測試機】CPA 人員頁拆成 Client 同 Staff

<http://3.114.114.143/attendance/clients>

- 側欄 Unit Management 拆成 Client Management 同 Staff Management
- 學生相關用字改成 Client，包括「學生」
- 正式機仍然係一個 Unit Management

### 【測試機】CPA 發票付款字可以跟 Team 改

<http://3.114.114.143/attendance/locations>

- CPA 借項通知單的圓形 logo、信頭同頁尾都係 DRJ 的圖，版面跟公司樣稿
- Extra Details 可以加 `invoice_payment` 改付款方法。唔寫，付款方法就留空
- 借項通知單 BILL TO 名稱一行、地址下一行，地址太長會在逗號後面換行，同一段地址不會被拆開，名稱不附編號，單號係「客戶編號/單號/年份」，日期係日/月/年
- 正式機的學費發票不變

## 13/11/2026

### 【測試機】CPA 課程頁改叫 Service，班次改叫 Line item

<http://3.114.114.143/attendance/courses>

- CPA 品牌側欄同課程管理頁的 Course 會顯示做 Service，Class 會顯示做 Line item。新增 Service 時，Subject 叫 Group、Chinese name 叫 Name、English name 叫 Sub-name。新增 Line item 時，Chinese name 叫 Name、English name 叫 Sub-name、Campus 叫 Team、Teacher / staff 叫 staff。名冊標題叫 Recurring Service。Join a student 叫 Enrollment，Student 叫 Client，Find student 叫 Find Client。狀態只顯示 Active 或 Inactive。發票頁標題叫 Invoices，帳單表 Student 叫 Client，地點選擇叫 Team，All locations 叫 All Teams。帳單表 Tutor 叫 Staff。手動發票的 Student name 叫 Client、Tutor 叫 Staff、Location 叫 Team、Month 叫 Period、Add a class 叫 Add Item。價錢可以填 0。收據同新增收據的 Location 叫 Team、Student 叫 Client、All locations 叫 All Teams、Month 叫 Period。正式機仍然係原本用字。

### 【測試機】QR Codes 可以按地點篩

<http://3.114.114.143/attendance/qr-codes>

- QR Codes 頁多咗 Location，可以只睇某個地點註冊嘅學生同員工，再揀選列印

### 【測試機】學費發票同課程表睇到長名

<http://3.114.114.143/attendance/invoices>

<http://3.114.114.143/attendance/courses>

- 學費發票列表嘅學生名同課程名闊咗，長公司名、長班名可以顯示兩行
- 課程管理入面班次表嘅名稱欄闊咗，右邊唔會再留一截空位

### 【測試機】CPA 發票：長編號同借項通知單

<http://3.114.114.143/attendance/invoices>

- CPA 品牌可以手打 `202611001` 呢類較長發票編號
- CPA 列印改為 DRJ 借項通知單（Bill To、編號、日期、描述、金額、總額跟張單；公司地址同付款方法係固定）
- 開新手動發票仍然係一行，可以加到 100 行
- 正式機（aqua）發票版面同編號上限冇變

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
