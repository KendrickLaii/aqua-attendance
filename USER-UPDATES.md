# 系統更新紀錄（用戶版）

俾用戶睇嘅更新公告，最新喺最上面，可以直接複製去 WhatsApp。技術細節見 [CHANGELOG.md](CHANGELOG.md)。

- **正式機**：<http://57.180.114.85>
- **測試機**：<http://3.114.114.143>（新功能會先喺度試用）

---

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
