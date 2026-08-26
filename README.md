# Retail Demand Forecasting Dashboard

**A Power BI interactive dashboard demonstrating LightGBM demand forecasting model performance against baseline methods.**

<img width="1294" height="727" alt="image" src="https://github.com/user-attachments/assets/79b876e9-05a7-49a1-a3c0-b99b54903e5f" />
<img width="1290" height="725" alt="image" src="https://github.com/user-attachments/assets/8fc31b67-62b4-4171-bfe1-fcd2244ec87b" />
<img width="1296" height="726" alt="image" src="https://github.com/user-attachments/assets/956d3698-d883-4b48-ba60-011dbf0970b5" />


---

## 📊 Overview

This dashboard provides a comprehensive evaluation of a LightGBM-based demand forecasting model built for retail supply chain optimization. It compares the model's performance against a baseline method across 28-day forecast windows, multiple product categories, and 3,049 individual SKUs.

**Key Performance**: The LightGBM model achieves **73.8% WMAPE** (Weighted Mean Absolute Percentage Error) versus baseline's **76.6%**, a **2.8 percentage-point improvement**—with a slight -4.1% bias indicating conservative under-forecasting.

---

## 🎯 Three-Page Design

### **Page 1: Forecast Accuracy** (Hero Page)
The executive showcase. Proves the model works at a glance.

**Visuals:**
- **4 KPI Cards**: WMAPE (LightGBM), WMAPE (Baseline), Improvement (pp), Bias
- **Line Chart**: "Forecast vs Actual (28-day horizon)" — Three series tracking actual vs. both forecast methods
- **Clustered Bar**: "WMAPE by Category & Model" — Accuracy win across FOODS, HOBBIES, HOUSEHOLD
- **Matrix/Scorecard**: Detailed accuracy breakdown by category

**Story**: LightGBM beats baseline consistently. Model is slightly conservative but stable.

---

### **Page 2: Demand & Sales Trends**
Shift to business analytics. Understand what's selling and identify revenue leaders.

**Visuals:**
- **3 KPI Cards**: Total Revenue ($5.18M), Total Units (2M), Avg Selling Price ($3.18)
- **Line Chart**: "Total Units by Day and cat_id" — Seasonality, category mix, trends
- **Data Table**: "Top 15 SKUs by Revenue" — Item-level revenue, units, and pricing
- **Stacked Column**: "Total Revenue by Year and cat_id" — Year-over-year category breakdown

**Story**: Demand is seasonal with weekly peaks. FOODS leads volume; revenue is concentrated in ~15 power items.

---

### **Page 3: SKU Drilldown**
Deep dive for planners. Pick one product, see its forecast quality over 28 days.

**Visuals:**
- **Slicer**: Single-select on item_id (searchable, 3,049 items)
- **3 KPI Cards**: WMAPE, Bias, Forecast Accuracy % for selected SKU
- **Line Chart**: "Total Units, Forecast (LightGBM) and Actual by Day" — History + forecast window

**Story**: Forecast accuracy varies by item (30%–96%). High-accuracy items are safe for replenishment; low-accuracy items need manual review.

---

## 🔧 Data Architecture

### Star Schema
```
dim_calendar (10 columns)
├─ date, dnum, wday, weekday, month, year, is_forecast_period, is_weekend
├─ event_name, event_type
│
dim_item (3 columns)
├─ item_id (3,049 unique)
├─ dept_id
└─ cat_id (FOODS, HOBBIES, HOUSEHOLD)

dim_store (2 columns)
├─ store_id (1 store: CA_1)
└─ state_id (CA)

fact_sales (6 columns, 1.1M rows)
├─ date FK→ dim_calendar
├─ item_id FK→ dim_item
├─ store_id FK→ dim_store
├─ units, sell_price, revenue

fact_forecast (9 columns, 85K rows — 28-day window)
├─ date FK→ dim_calendar
├─ item_id FK→ dim_item
├─ store_id FK→ dim_store
├─ cat_id (redundant, for convenience)
├─ actual, forecast_lgbm, forecast_baseline
└─ abs_err_lgbm, abs_err_baseline
```

### Relationships
All one-directional (dimension → fact), many-to-one cardinality, single active per pair:
- `dim_calendar[date]` → `fact_sales[date]` & `fact_forecast[date]`
- `dim_item[item_id]` → `fact_sales[item_id]` & `fact_forecast[item_id]`
- `dim_store[store_id]` → `fact_sales[store_id]` & `fact_forecast[store_id]`

---

## 📐 DAX Measures (15 Total)

All measures live in the `_Measures` table, organized by display folder.

### **Sales Metrics**
```dax
Total Units = SUM ( fact_sales[units] )
Total Revenue = SUM ( fact_sales[revenue] )
Avg Selling Price = DIVIDE ( [Total Revenue], [Total Units] )
```

### **Forecast Volume**
```dax
Actual = SUM ( fact_forecast[actual] )
Forecast (LightGBM) = SUM ( fact_forecast[forecast_lgbm] )
Forecast (Baseline) = SUM ( fact_forecast[forecast_baseline] )
```

### **Accuracy Metrics**
```dax
Abs Error (LightGBM) = SUM ( fact_forecast[abs_err_lgbm] )
Abs Error (Baseline) = SUM ( fact_forecast[abs_err_baseline] )

WMAPE (LightGBM) = DIVIDE ( [Abs Error (LightGBM)], [Actual] )
WMAPE (Baseline) = DIVIDE ( [Abs Error (Baseline)], [Actual] )

Forecast Accuracy % (LightGBM) = 1 - [WMAPE (LightGBM)]
WMAPE Improvement (pp) = [WMAPE (Baseline)] - [WMAPE (LightGBM)]

Bias (LightGBM) = DIVIDE ( [Forecast (LightGBM)] - [Actual], [Actual] )
Bias (Baseline) = DIVIDE ( [Forecast (Baseline)] - [Actual], [Actual] )

MAE (LightGBM) = AVERAGE ( fact_forecast[abs_err_lgbm] )
```

### Formatting
- **WMAPE, Forecast Accuracy %, Bias**: `0.0%`
- **Total Revenue, Avg Selling Price**: `$#,##0.00`
- **Total Units, Actual, Forecast**: `#,##0` (whole number)

---

## 🎨 Visual Design

### Color Language
| Element | Color | Role |
|---------|-------|------|
| LightGBM Forecast | Bright Blue (#0078D4) | Hero model |
| Baseline Forecast | Dark Navy (#003D7A) | Comparison |
| Actual Demand | Orange (#FF7F00) | Ground truth |
| Supporting Charts | Blue | Emphasis |

**Principle**: Consistent color across all pages so viewers learn the meaning in 30 seconds.

### Typography
- **Titles**: Statement-form. E.g., "LightGBM cuts forecast error by 2.8 percentage points" not "WMAPE Comparison"
- **Cards**: 60–72pt numbers; metric label below in grey
- **Charts**: Clear axis labels, legend, minimal gridlines

### Interactivity
- **Pages 1–2**: Global slicers (Date range, Category, Store) filter all visuals
- **Page 3**: Item-level slicer drives the narrative; no cross-page filtering to keep intent explicit
- **No drill-through**: Users manually select what they want to explore

---

## 📈 Key Insights

### Model Performance
- **LightGBM wins**: 2.8 pp WMAPE improvement over baseline (76.6% → 73.8%)
- **Category variance**: FOODS 66.4%, HOUSEHOLD 85.1%, **HOBBIES 96.9%** (opportunity for improvement)
- **Bias**: -4.1% (model tends to under-forecast; conservative, safer than overstock)

### Business Patterns
- **Seasonality**: Clear weekly peaks mid-week, troughs on weekends
- **Revenue concentration**: Top 15 SKUs drive $568K–$1.5K each; long tail of 3,049 items
- **Forecast reliability**: 30%–96% accuracy per SKU; high variability indicates category/price-sensitivity needs deeper investigation

### Recommendations
1. **For Executives**: Use Page 1 to communicate model ROI; 2.8 pp improvement justifies engineering investment
2. **For Planners**: High-accuracy SKUs (>80%) → use forecast directly for replenishment; Low-accuracy (<40%) → manual override + buffer stock
3. **For Data Scientists**: HOBBIES category is the next frontier; retrain with category-specific features or segment further

---

## 🚀 Getting Started

### Requirements
- **Power BI Desktop** (latest version recommended)
- **Data**: CSV files (`dim_calendar.csv`, `dim_item.csv`, `dim_store.csv`, `fact_sales.csv`, `fact_forecast.csv`)
- **Connection**: Local Power BI Desktop instance

### Loading the Model
1. Open `Retail Dashboard.pbix` in Power BI Desktop
2. All measures and relationships are pre-built in the semantic model
3. Data is imported; refresh weekly if fact tables update

### Viewing the Report
1. Switch to **Report view** (default when opening)
2. Use the **Date range slicer** at top-left to filter the forecast window
3. Select categories and store via checkboxes
4. On Page 3, search the item slicer to pick individual SKUs

---

## 📊 Data Lineage

```
CSV Files
    ├─ dim_calendar.csv → dim_calendar (10 cols, 1 partition)
    ├─ dim_item.csv → dim_item (3 cols, 3,049 rows)
    ├─ dim_store.csv → dim_store (2 cols, 1 row)
    ├─ fact_sales.csv → fact_sales (6 cols, 1.1M rows)
    └─ fact_forecast.csv → fact_forecast (9 cols, 85K rows)
                                              ↓
                                    Star Schema (Relationships)
                                              ↓
                                        DAX Measures (15)
                                              ↓
                                    Power BI Visuals (3 Pages)
```

---

## 🔄 Refresh Strategy

| Table | Frequency | Reason |
|-------|-----------|--------|
| `dim_calendar` | Annual (Jan 1) | Static; one year of dates pre-loaded |
| `dim_item` | Quarterly | New SKUs added periodically |
| `dim_store` | Annually | Store count rarely changes |
| `fact_sales` | Weekly | Historical data accumulates as year progresses |
| `fact_forecast` | Daily | Rolling 28-day window; new actuals arrive daily |

---

## 🎓 Use Cases

### Sales Planning
- Identify seasonality peaks to time promotions
- Spot slow-moving items for clearance or discontinuation
- Validate demand assumptions from planners against forecast

### Inventory Management
- High-accuracy SKUs: Use forecast directly for replenishment
- Low-accuracy SKUs: Add safety stock or request manual overrides
- Monitor bias drift; if model starts over-forecasting, investigate

### Model Governance
- Track WMAPE by category over time to detect model degradation
- Compare actual vs. forecast at week-end to assess residual patterns
- Escalate HOBBIES items to data science for retraining

### Executive Reporting
- Dashboard snapshot: "Model accuracy at 73.8%, up 2.8 pp from baseline"
- Business impact: Link forecast improvement to inventory turns, stockouts prevented
- Forecast vs. actual reconciliation for CFO quarterly reviews

---

## 🛠️ Technical Stack

| Component | Technology |
|-----------|-----------|
| BI Platform | Power BI Desktop |
| Data Model | Tabular (DAX) |
| Measures | 15 DAX formulas |
| Schema | Star (1 fact + 3 dims, + 2 helper tables) |
| Forecast Method | LightGBM (external model; pre-computed) |
| Baseline | Naive/statistical forecast (pre-computed) |

---

## 📁 Files & Artifacts

```
.
├── Retail Dashboard.pbix          # Main Power BI report (model + visuals)
├── README.md                      # This file
├── Retail_Dashboard_Design_Doc.docx # Detailed design documentation
├── data/
│   ├── dim_calendar.csv
│   ├── dim_item.csv
│   ├── dim_store.csv
│   ├── fact_sales.csv
│   └── fact_forecast.csv
└── DAX_measures.md                # Measure reference
```

---

## 🔐 Data Privacy & Security

- **No PII**: All data is at item, store, and date level; no customer-level details
- **Access**: Share `.pbix` file via secure channel; Power BI dataset permissions enforced per viewer
- **Refresh**: Requires local Power BI Desktop; no cloud dependency by default
- **Backup**: Version the `.pbix` file in git; data CSVs in data lake with standard backups

---

## 📋 Future Enhancements

1. **Page 4: Feature Importance** — Visualize which variables drive LightGBM predictions (using `feature_importance` table)
2. **External Drivers** — Integrate promotions, holidays, competitor actions to explain forecast misses
3. **Alerts & KPIs** — "WMAPE for item X exceeded 80% this week" notifications
4. **Model Retraining Loop** — Export forecast-to-actual reconciliation nightly; feed back into model training
5. **Mobile View** — Optimize report for mobile; focus on Page 1 KPIs and Page 3 SKU search
6. **What-If Analysis** — Scenario planning: "If we apply a 10% discount to HOBBIES, what's the forecast impact?"

---

**Last Updated**: August 2026  
**Dashboard Version**: 1.0  
**Data Coverage**: 26 June 2011 – 22 May 2016
