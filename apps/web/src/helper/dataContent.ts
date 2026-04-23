import type { DataContentList } from '@/types/dataContent'
export const dataContentNameList: DataContentList[] = [
    {
        dataContentType: 'info',
        tableType: 'breakdownCategory',
        tableName: 'General (Category)',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: 'breakdownDisplayName',
        tableName: 'General (Display name)',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: 'tax',
        tableName: 'Gen. w/o subtotal',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: '2Columns',
        tableName: '2 Columns',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: '2ColumnsWithoutSubtotal',
        tableName: '2 Col w/o subtotal',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: '3Columns',
        tableName: '3 Columns',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: 'S383',
        tableName: 'S. 383(1)(d) disclosure',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: 'ppe',
        tableName: 'PPE disclosure',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: 'EQ',
        tableName: 'Change in Equity',
        enable: true,
    },
    {
        dataContentType: 'info',
        tableType: 'general',
        tableName: 'General',
        enable: false,
    },
    {
        dataContentType: 'info',
        tableType: 'due',
        tableName: 'Amount Due from Related Parties',
        enable: false,
    },
    {
        dataContentType: 'info',
        tableType: 'iis',
        tableName: 'Investment in Subsidary',
        enable: false,
    },
    {
        dataContentType: 'info',
        tableType: 'signature',
        tableName: 'Signature',
        enable: true,
    },
]
export const getTableDataByTableType = (tableType: string) => {
    switch(tableType){
        // General (Category)
        case 'breakdownCategory':
          return breakdownTableData()
        // General (Display name)
        case 'breakdownDisplayName':
          return breakdownTableData()
        // 2 Columns
        case '2Columns':
          return customizedTableData(tableType)
        // 2 Col w/o subtotal
        case '2ColumnsWithoutSubtotal':
          return customizedTableData(tableType)
        // 3 Columns
        case '3Columns':
          return customizedTableData(tableType)
        // 4 Columns
        case '4Columns':
          return customizedTableData(tableType)
        // S. 383(1)(d) disclosure
        case 'S383':
          return customizedTableData(tableType)
        // PPE disclosure
        case 'ppe':
          return ppeTableData()
        // Signature
        case 'signature':
          return signatureTableData()
        // Change in Equity
        case 'EQ':
          return EQTableData()
        // Gen. w/o subtotal
        case 'tax':
          return taxTableData()
        default:
          return breakdownTableData()
      }
}
//tableType: breakdownCategory,breakdownDisplayName
export function breakdownTableData() {
    return [
      {
        titleSelect: true,
        name: "",
        note: "Note",
        noteType: "title",
        this: "Current Year",
        last: "Prior Year",
      },
      {
        name: "",
        note: "",
        noteType: "currency",
        this: "Currency",
        last: "Currency",
      },
      {
        itemSelect: true, // category显示
        name: "",
        note: "",
        noteType: "input",
        yearSum: true,
        this: "",
        last: "",
        category: true,
      },
      {
        itemSelect: true, // 明细部分
        name: "",
        note: "",
        noteType: "input",
        type: "breakdown",
        yearSum: true,
        this: "",
        last: "",
        number: 1,
        noTotalNum: 1,
      },
      {
        total: true, // total部分
        type: "total",
        name: "",
        note: "",
        this: "",
        last: "",
      },
    ];
}
//tableType: EQ
export function EQTableData() {
    return [
        {
          titleSelect: true,
          name: "",
          note: "Note",
          noteType: "title",
          this: "Share capital",
          last: "Retained earnings",
          sumTotal: "Total",
        },
        {
          name: "",
          note: "",
          noteType: "currency",
          this: "Currency",
          last: "Currency",
          sumTotal: "Currency",
        },
        {
          itemSelect: true,
          dateShow: true,
          yearSum: true,
          name: 'Year Start Date(Job file)',
          nameType: "priorYearSum", 
        //   name: "At " + formattedDate(params.route.query.startYear),
          note: "",
          noteType: "input",
          this: "",
          last: "",
          sumTotal: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Allotment",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          number: 1,
          noTotalNum: 1,
          sumTotal: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Dividend paid",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          number: 2,
          noTotalNum: 2,
          sumTotal: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Loss for the year",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          number: 3,
          noTotalNum: 3,
          sumTotal: "",
          profitLossRow: true,
        },
        {
          itemSelect: true, // category显示
          total: true, // total部分
          dateShow: true,
          name: 'Year End Date(Job file)',
          nameType: "financeYearSum", 
        //   name: "At " + formattedDate(params.route.query.endYear),
          note: "",
          this: "",
          last: "",
          sumTotal: "-",
        },
    ]
}
//tableType: tax
export function taxTableData() {
    return [
        {
          contentTitle: true, // 显示 'content' 标题
          titleSelect: true,
          name: "",
          title: "Content",
          note: "Note",
          noteType: "title",
          this: "Current Year",
          last: "Prior Year",
        },
        {
          name: "",
          note: "",
          noteType: "currency",
          this: "Currency",
          last: "Currency",
        },
        {
          itemSelect: true, // 明细部分
          name: "",
          note: "",
          noteType: "input",
          type: "breakdown",
          yearSum: true,
          this: "",
          last: "",
          number: 1,
          noTotalNum: 1,
        },
        // {
        //   total: true, // total部分
        //   type: "total",
        //   name: "",
        //   note: "",
        //   this: "",
        //   last: "",
        // },
        {
          type: "blankRow",
          name: "",
          note: "",
          this: "",
          last: "",
        },
      ]
}
//tableType: 2Columns,2ColumnsWithoutSubtotal,3Columns,S383
export function customizedTableData(tableType:string){
  const list = [
    {
      name: "",
      referenceName: "",
      note: "",
      noteType: "reference",
      this: "",
      last: "",
      firstColumnHeader:"",
      secondColumnHeader:"",
    },
    {
      titleSelect: true,
      name: "",
      note: "Note",
      noteType: "title",
      this: "Current Year",
      last: "Prior Year",
      firstColumnHeader:"",
      secondColumnHeader: tableType == "S383" ? `Maximum outstanding amount during the Fiscal Year` : "",
    },
    {
      name: "",
      note: "",
      noteType: "currency",
      this: "Currency",
      last: "Currency",
      secondColumnCurrency: "Currency",
    },
    {
      itemSelect: true, // category显示
      name: "",
      note: "",
      noteType: "input",
      yearSum: true,
      this: "",
      last: "",
      category: true,
    },
    {
      itemSelect: true, // 明细部分
      name: "",
      detail:"",
      note: "",
      noteType: "input",
      type: "breakdown",
      yearSum: true,
      this: "",
      last: "",
      number: 1,
      noTotalNum: 1,
    },
    {
      total: true, // total部分
      type: "total",
      name: "",
      note: "",
      this: "",
      last: "",
    },
    {
      type: "blankRow",
      name: "",
      note: "",
      this: "",
      last: "",
    },
  ]
  if(tableType === "2ColumnsWithoutSubtotal"){
    const listWithoutSubtotal = [...list]
    const totalRowIndex = findTotalRowIndex(listWithoutSubtotal)
    console.log("pop the total row",listWithoutSubtotal)
    listWithoutSubtotal.splice(totalRowIndex, 1); //remove the total row
    return listWithoutSubtotal;
  }
  return list;
}
//tableType: ppe
export function ppeTableData(){
    return [
        {
          titleSelect: true,
          tableTitle: true,
          name: "",
          nameType: "ACDisplayName",
          note: "Note",
          border: "",
          noteType: "title",
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "Total",
        },
        {
          itemSelect: true,
          // category: true,
          name: "",
          note: "",
          border: "",
          noteType: "",
          nameType: "currency",
          this: "Currency", // 這個currency 根據 Profile data中的currency更改
          last: "Currency", // 這個currency 根據 Profile data中的currency更改
          displayList: [
            { name: "Currency" },
            { name: "Currency" },
            { name: "Currency" },
            { name: "Currency" },
          ],
          sumTotal: "Currency",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "AT COST",
          border: "",
          note: "",
          noteType: "break",
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
        },
        {
          itemSelect: true,
          dateShow: true,
          yearSum: true,
          name: 'Year Start Date(Job file)',
          // name: 'At '+this.$route.query.startYear,
        //   name: "At " + formattedDate(params.route.query.startYear),
          nameType: "ACStartDate",
          inpColor: "gray",
          note: "",
          noteType: "input",
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Addition",
          nameType: "Addition",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 1,
          noTotalNum: 1,
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Disposal",
          nameType: "Disposal",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 2,
          noTotalNum: 2,
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Write off",
          nameType: "Write off AC",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 3,
          noTotalNum: 3,
          sumTotal: "",
          border: "",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "oneLine",
        },
        {
          itemSelect: true, // category显示
          //total: true,    // total部分
          dateShow: true,
          name: 'Year End Date(Job file)',
        //   name: "At " + formattedDate(params.route.query.endYear),
          dashed: true,
          nameType: "ACEndDate",
          inpColor: "gray",
          note: "",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 3,
          noTotalNum: 3,
          sumTotal: "",
          border: "dash",
        },
        // *************************************************************************
        {
          tableTitle: true,
          itemSelect: true,
          name: "",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "ACCUMULATED DEPRECIATION",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true,
          dateShow: true,
          yearSum: true,
          name: 'Year Start Date(Job file)',
        //   name: "At " + formattedDate(params.route.query.startYear),
          nameType: "ADStartDate",
          note: "",
          inpColor: "gray",
          noteType: "input",
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Charge for the Fiscal Year",
          nameType: "Charge for the DATE",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 1,
          noTotalNum: 1,
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Write back upon disposal",
          nameType: "Write back upon disposal",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 2,
          noTotalNum: 2,
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // 明细部分
          name: "Write off",
          nameType: "Write off AD",
          note: "",
          noteType: "input",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 3,
          noTotalNum: 3,
          sumTotal: "",
          border: "",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "oneLine",
        },
        {
          itemSelect: true, // category显示
          total: true, // total部分
          dateShow: true,
          name: 'Year End Date(Job file)',
        //   name: "At " + formattedDate(params.route.query.endYear),
          dashed: true,
          border: "dash",
          nameType: "ADEndDate",
          inpColor: "gray",
          yearSum: true,
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          number: 3,
          noTotalNum: 3,
          sumTotal: "",
        },
        // *************************************************************************
        {
          tableTitle: true,
          itemSelect: true,
          name: "",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "NET BOOK VALUE",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true, // category显示
          total: true, // total部分
          dateShow: true,
          yearSum: true,
          name: 'Year End Date(Job file)',
        //   name: "At " + formattedDate(params.route.query.endYear),
          nameType: "NetBookStartDate",
          note: "",
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "double",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
        {
          itemSelect: true,         // category显示
          total: true,    // total部分
          dateShow: true,
          yearSum: true,
          name: 'Year Start Date(Job file)',
        //   name: "At " + formattedDate(params.route.query.L_year_end),
          nameType: "NetBookEndDate",
          note: "",
          noteType: "input",
          this: "",
          last: "",
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "double",
        },
        {
          tableTitle: true,
          itemSelect: true,
          name: "",
          note: "",
          noteType: "break",
          this: "", // 這個currency 根據 Profile data中的currency更改
          last: "", // 這個currency 根據 Profile data中的currency更改
          displayList: [{ name: "" }, { name: "" }, { name: "" }, { name: "" }],
          sumTotal: "",
          border: "",
        },
    ];
}
//tableType: signature
export function signatureTableData(){
  return [
    {
      footnote:"",
      headnote:"",
      name: "",
      position: "",
      signatureAlignment: "left",
      noteType: "reference",
    },
    {
      footnote:"Footnote",
      headnote:"Headnote",
      name: "Name",
      noteType: "title",
      position: "Position",
      titleSelect: true,
    },
    {
      footnote:"",
      headnote:"",
      itemSelect: true, //
      name: "",
      position: "",
      noteType: "input",
    },
  ]
}
function findTotalRowIndex(list:any[]){
  return list.findIndex(item => item.type === "total");
}
