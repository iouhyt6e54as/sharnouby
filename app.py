"""El-Sharnouby Group: executive dashboard (HVIA Task 02).  Run:  streamlit run app.py"""
import os, glob
import numpy as np, pandas as pd, plotly.express as px, plotly.graph_objects as go, streamlit as st
from plotly.subplots import make_subplots

st.set_page_config(page_title="El-Sharnouby Dashboard", page_icon="📊", layout="wide")
BLUE, GREEN, RED, AMBER = "#2f4ba0", "#1f8a70", "#c0392b", "#d98e04"
M = lambda x: f"{x/1e6:,.1f}M"

def show(fig, box=st):
    """Plotly chart that stretches to the container on both old and new Streamlit versions."""
    try: box.plotly_chart(fig, width="stretch")
    except TypeError: show(fig, box)

# ------------------------------------------------------------------ data
folder = st.sidebar.text_input("Data folder", "sharnouby_data")
if not os.path.exists(os.path.join(folder, "Sales_Transactions.csv")):
    st.error(f"Folder '{folder}' with the CSV files was not found. Put it next to app.py or fix the path in the sidebar."); st.stop()

def fy_label(d):
    return "FY" + ((d.dt.year + (d.dt.month >= 10).astype(int)) % 100).astype(str)

@st.cache_data(show_spinner="Loading data...")
def load(path):
    t = {os.path.splitext(os.path.basename(f))[0]: pd.read_csv(f, keep_default_na=False, na_values=[""]) for f in glob.glob(os.path.join(path, "*.csv"))}
    for n, cols in {"Sales_Transactions": ["Order_Date", "Return_Date"], "Purchase_Orders": ["Order_Date", "Promised_Date", "Actual_Receipt_Date"],
                    "Production_Orders": ["Start_Date", "Due_Date", "Completion_Date"], "Marketing": ["Start_Date"], "Quality": ["Inspection_Date"],
                    "Printing_Batches": ["Print_Date"], "Machine_Downtime": ["Date"]}.items():
        for c in cols: t[n][c] = pd.to_datetime(t[n][c], errors="coerce")
    s = t["Sales_Transactions"]; s["FY"] = fy_label(s.Order_Date); s["Month"] = s.Order_Date.dt.to_period("M").dt.to_timestamp()
    s["Customer_Type"] = s.Customer_ID.map(t["Customers"].set_index("Customer_ID").Customer_Type)
    return t
T = load(folder); S = T["Sales_Transactions"]; PM = T["Product_Master"].set_index("Product_ID")

# ------------------------------------------------------------------ filters
st.sidebar.header("Filters")
fys = st.sidebar.multiselect("Fiscal year (Oct to Sep)", sorted(S.FY.unique()), default=sorted(S.FY.unique()))
chs = st.sidebar.multiselect("Channel", sorted(S.Channel.unique()), default=sorted(S.Channel.unique()))
sf = S[S.FY.isin(fys) & S.Channel.isin(chs)]
if sf.empty: st.warning("No data for this selection."); st.stop()
st.sidebar.caption("Filters apply to the Overview and Customers tabs. Operations, Marketing and Supply show the full period.")

st.title("El-Sharnouby Group: Executive Dashboard")
st.caption("HVIA Task 02 | modelled training data | FY = October to September | all figures computed from the source tables")

def kpi(df):
    n, g = df.Net_Sales_EGP.sum(), df.Gross_Profit_EGP.sum()
    return n, g, g / n * 100 if n else 0, df.Customer_ID.nunique(), df.Is_Returned.mean() * 100 if "Is_Returned" in df else 0
S["Is_Returned"] = (S.Returned == "Yes").astype(int); sf = S[S.FY.isin(fys) & S.Channel.isin(chs)]
n, g, mg, cu, rr = kpi(sf)
c = st.columns(5)
c[0].metric("Net sales", M(n) + " EGP"); c[1].metric("Gross profit", M(g) + " EGP"); c[2].metric("Gross margin", f"{mg:.1f}%")
c[3].metric("Active customers", f"{cu:,}"); c[4].metric("Return rate", f"{rr:.1f}%")
if len(fys) == 1 and int(fys[0][2:]) > int(sorted(S.FY.unique())[0][2:]):
    pv = "FY" + str(int(fys[0][2:]) - 1); pn = kpi(S[(S.FY == pv) & S.Channel.isin(chs)])[0]
    st.caption(f"Net sales vs {pv}: {(n / pn - 1) * 100:+.1f}%")

tabs = st.tabs(["Overview", "Customers", "Marketing", "Operations", "Supply Risk Radar"])

# ------------------------------------------------------------------ 1 overview
with tabs[0]:
    m = sf.groupby("Month").agg(sales=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum")).reset_index(); m["margin"] = m.gp / m.sales * 100
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_bar(x=m.Month, y=m.sales / 1e6, name="Net sales (M EGP)", marker_color=BLUE)
    fig.add_scatter(x=m.Month, y=m.margin, name="Gross margin %", line=dict(color=AMBER), secondary_y=True)
    fig.update_layout(title="Net sales and gross margin by month", legend=dict(orientation="h"), height=380); show(fig, st)
    a, b = st.columns(2)
    ch = sf.groupby("Channel").agg(n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum")); ch["% of sales"] = ch.n / ch.n.sum() * 100; ch["% of gross profit"] = ch.g / ch.g.sum() * 100; ch["margin %"] = ch.g / ch.n * 100
    show(px.bar(ch.reset_index(), x="Channel", y=["% of sales", "% of gross profit"], barmode="group", title="Share of sales vs share of profit", color_discrete_sequence=[BLUE, GREEN]), a)
    pf = sf.groupby("Product_Family").agg(n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum")); pf["margin %"] = pf.g / pf.n * 100
    show(px.bar(pf.reset_index().sort_values("n"), y="Product_Family", x="n", color="margin %", orientation="h", title="Net sales by family (colour = margin %)", color_continuous_scale="RdYlGn"), b)
    bands = pd.cut(sf.Discount_Pct, [-.001, 0, .1, .2, .3, .4], labels=["0%", "1-10%", "11-20%", "21-30%", "31-40%"])
    d = sf.assign(band=bands).groupby(["Channel", "band"], observed=True).agg(n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum")).reset_index(); d["margin %"] = d.g / d.n * 100
    show(px.line(d, x="band", y="margin %", color="Channel", markers=True, title="Gross margin by discount band"), st)
    neg = sf[sf.Gross_Profit_EGP < 0]
    st.info(f"{len(neg):,} loss-making lines ({len(neg)/len(sf):.1%}) lose {-neg.Gross_Profit_EGP.sum():,.0f} EGP in this selection.")
    st.dataframe(ch[["n", "% of sales", "% of gross profit", "margin %"]].rename(columns={"n": "net sales EGP"}).round(1))

# ------------------------------------------------------------------ 2 customers
with tabs[1]:
    snap = S.Order_Date.max() + pd.Timedelta(days=1)
    cu_ = sf.groupby("Customer_ID").agg(first=("Order_Date", "min"), last=("Order_Date", "max"), orders=("Invoice_ID", "nunique"), net=("Net_Sales_EGP", "sum"), gp=("Gross_Profit_EGP", "sum"))
    cu_ = cu_.join(T["Customers"].set_index("Customer_ID")[["Customer_Type", "Governorate", "Acquisition_Channel", "Consent_Status"]])
    cu_["recency"] = (snap - cu_["last"]).dt.days
    rc = cu_[cu_.Customer_Type == "Retail"].copy()
    if len(rc) < 50: st.info("Too few retail customers in this selection for RFM.")
    else:
        sc = lambda x, asc=True: pd.qcut(x.rank(method="first", ascending=asc), 5, labels=[1, 2, 3, 4, 5]).astype(int)
        rc["R"], rc["F"] = sc(rc.recency, False), sc(rc.orders)
        def seg(r):
            if r.R >= 4 and r.F >= 4: return "Champions"
            if r.R >= 3 and r.F >= 4: return "Loyal"
            if r.R >= 4 and r.F <= 2: return "New / Promising"
            if r.R >= 3 and r.F == 3: return "Potential Loyalists"
            if r.R <= 2 and r.F >= 4: return "Cannot Lose"
            if r.R <= 2 and r.F == 3: return "At Risk"
            return "Hibernating" if r.R <= 2 else "Need Attention"
        rc["segment"] = rc.apply(seg, axis=1)
        k = st.columns(3); k[0].metric("Retail customers", f"{len(rc):,}"); k[1].metric("Repeat rate (2+ orders)", f"{(rc.orders >= 2).mean():.0%}"); k[2].metric("Median orders", f"{rc.orders.median():.0f}")
        sg = rc.groupby("segment").agg(customers=("orders", "size"), net=("net", "sum")).reset_index()
        a, b = st.columns(2)
        show(px.bar(sg.sort_values("net"), y="segment", x="net", orientation="h", title="RFM segments: net sales (EGP)", color_discrete_sequence=[BLUE]), a)
        show(px.pie(sg, names="segment", values="customers", hole=.5, title="RFM segments: customers"), b)
        lapse = st.slider("Lapsed = no purchase for more than N days", 60, 365, 180, 15)
        win = rc[(rc.recency > lapse) & (rc.Consent_Status == "Opted-in") & (rc.orders >= 2)].sort_values("gp", ascending=False)
        st.write(f"**Win-back list:** {len(win):,} opted-in customers with 2+ orders lapsed for more than {lapse} days (historical gross profit {win.gp.sum():,.0f} EGP).")
        st.dataframe(win.head(200)[["Governorate", "Acquisition_Channel", "orders", "net", "gp", "recency", "segment"]].round(0))
        st.download_button("Download win-back list (CSV)", win.reset_index().to_csv(index=False), "winback_list.csv")
    geo = sf[sf.Channel != "Wholesale"].groupby("Customer_Governorate").Net_Sales_EGP.sum().sort_values().tail(12).reset_index()
    show(px.bar(geo, y="Customer_Governorate", x="Net_Sales_EGP", orientation="h", title="Direct (Retail + Online) demand by governorate", color_discrete_sequence=[GREEN]), st)

# ------------------------------------------------------------------ 3 marketing
with tabs[2]:
    mk = T["Marketing"].copy(); ue = S.groupby("Product_ID").agg(n=("Net_Sales_EGP", "sum"), c=("Estimated_COGS_EGP", "sum")); ue["mg"] = 1 - ue.c / ue.n
    mk["gp"] = mk.Attributed_Revenue_EGP * mk.Product_ID.map(ue.mg); mk["contribution"] = mk.gp - mk.Spend_EGP; mk["ROAS"] = mk.Attributed_Revenue_EGP / mk.Spend_EGP
    pl = st.multiselect("Platforms", sorted(mk.Platform.unique()), default=sorted(mk.Platform.unique())); mk = mk[mk.Platform.isin(pl)]
    k = st.columns(4); k[0].metric("Spend", M(mk.Spend_EGP.sum())); k[1].metric("Blended ROAS", f"{mk.Attributed_Revenue_EGP.sum()/mk.Spend_EGP.sum():.2f}x")
    k[2].metric("Contribution after margin", f"{mk.contribution.sum()/1e6:,.2f}M"); k[3].metric("Campaigns losing money", f"{(mk.contribution < 0).sum()} of {len(mk)}")
    pt = mk.groupby("Platform").agg(spend=("Spend_EGP", "sum"), revenue=("Attributed_Revenue_EGP", "sum"), contribution=("contribution", "sum")).reset_index(); pt["ROAS"] = pt.revenue / pt.spend
    a, b = st.columns(2)
    show(px.bar(pt.sort_values("contribution"), y="Platform", x="contribution", orientation="h", title="Contribution after product margin (EGP)", color="contribution", color_continuous_scale="RdYlGn"), a)
    show(px.scatter(mk, x="Spend_EGP", y="ROAS", color="Platform", log_x=True, hover_data=["Campaign_ID"], title="Every campaign: spend vs ROAS"), b)
    st.caption("ROAS uses platform-attributed revenue, which exceeds total direct sales: treat it as an upper bound and validate with a holdout test.")
    st.dataframe(pt.round(2))

# ------------------------------------------------------------------ 4 operations
with tabs[3]:
    pr = T["Production_Orders"].copy(); pr["late"] = pr.Delay_Days > 0
    k = st.columns(4); k[0].metric("Orders", f"{len(pr):,}"); k[1].metric("Plan attainment", f"{pr.Produced_Qty.sum()/pr.Planned_Qty.sum():.1%}")
    k[2].metric("Orders finishing late", f"{pr.late.mean():.1%}"); k[3].metric("Reject rate", f"{pr.Rejected_Qty.sum()/pr.Produced_Qty.sum():.2%}")
    bn = pr[pr.Primary_Bottleneck != "None"].groupby("Primary_Bottleneck").Delay_Days.sum().sort_values(ascending=False).reset_index()
    a, b = st.columns(2)
    show(px.bar(bn, x="Primary_Bottleneck", y="Delay_Days", title="Delay days by bottleneck stage", color_discrete_sequence=[BLUE]), a)
    ln = pr.groupby("Line_ID").agg(efficiency=("Efficiency_Pct", "mean"), late=("late", "mean"), overtime=("Overtime_Hours", "sum")).reset_index(); ln["late"] *= 100
    show(px.bar(ln, x="Line_ID", y="late", title="% of orders late by line", color_discrete_sequence=[RED]), b)
    st.dataframe(ln.round(2))
    q = T["Quality"]; qd = q[q.Defect_Type != "None"].groupby("Defect_Type").Estimated_Loss_EGP.sum().sort_values(ascending=False).reset_index()
    pb = T["Printing_Batches"]; mc = pb.groupby("Machine_ID").agg(printed=("Printed_Qty", "sum"), good=("Good_Qty", "sum")).reset_index(); mc["yield %"] = mc.good / mc.printed * 100
    a, b = st.columns(2)
    show(px.bar(qd, x="Defect_Type", y="Estimated_Loss_EGP", title="QC loss by defect type (EGP)", color_discrete_sequence=[AMBER]), a)
    show(px.bar(mc, x="Machine_ID", y="yield %", title="Print yield by machine (%)", color_discrete_sequence=[GREEN]).update_yaxes(range=[mc["yield %"].min() - 1, 100]), b)
    dt = T["Machine_Downtime"]; dr = dt[dt.Machine_ID.isin(pb.Machine_ID.unique())].groupby("Reason").Downtime_Hours.sum().sort_values(ascending=False).reset_index()
    show(px.bar(dr, x="Reason", y="Downtime_Hours", title="Printing downtime hours by reason", color_discrete_sequence=[BLUE]), st)

# ------------------------------------------------------------------ 5 supply + radar
with tabs[4]:
    po = T["Purchase_Orders"].copy(); mat = T["Materials"].set_index("Material_ID"); bom = T["Product_BOM"]
    po["lead"] = (po.Actual_Receipt_Date - po.Order_Date).dt.days; po["delay"] = (po.Actual_Receipt_Date - po.Promised_Date).dt.days
    po["on_time"] = po.delay <= 0; po["otif"] = po.on_time & (po.Accepted_Qty / po.Ordered_Qty >= .97)
    k = st.columns(3); k[0].metric("On time", f"{po.on_time.mean():.0%}"); k[1].metric("On time and in full", f"{po.otif.mean():.0%}"); k[2].metric("Avg delay when late", f"{po[po.delay > 0].delay.mean():.1f} days")
    so = po.groupby("Supplier_ID").otif.mean().mul(100).sort_values().reset_index()
    show(px.bar(so, x="Supplier_ID", y="otif", title="Supplier on-time-in-full (%)", color="otif", color_continuous_scale="RdYlGn"), st)
    st.subheader("Demand-to-Supply Risk Radar")
    st.caption("Forecast (trend x seasonality) x BOM -> material need -> real lead-time behaviour -> order-by dates and gross profit at risk.")
    p = st.columns(4)
    y0 = round(pr.Rejected_Qty.sum() / pr.Produced_Qty.sum() * 100 * 2) / 2; c0 = int(round(((pr.Completion_Date - pr.Start_Date).dt.days + 1).mean()))
    yl = p[0].slider("Production yield loss %", 0.0, 10.0, float(y0), .5) / 100; cyc = p[1].slider("Production cycle (days)", 0, 40, c0); hnd = p[2].slider("Handling buffer (days)", 0, 14, 3)
    asof = p[3].date_input("Planning date", S.Order_Date.max().date() + pd.Timedelta(days=1))

    @st.cache_data
    def forecast(path):
        y = S.pivot_table(index="Product_ID", columns="Month", values="Quantity", aggfunc="sum").fillna(0); n_ = y.shape[1]; t_ = np.arange(n_); out = []
        for v in y.values:
            b_, a_ = np.polyfit(t_, v, 1); tr = np.maximum(a_ + b_ * t_, 1e-6); se = np.array([(v / tr)[i::12].mean() for i in range(12)])
            f = np.arange(n_, n_ + 3); out.append(np.maximum((a_ + b_ * f) * se[f % 12], 0))
        months = pd.date_range(y.columns[-1] + pd.DateOffset(months=1), periods=3, freq="MS")
        return pd.DataFrame(out, index=y.index, columns=months)
    fc = forecast(folder); mcols = list(fc.columns)
    req = bom.merge(fc.reset_index(), on="Product_ID")
    for m_ in mcols: req[m_] = req[m_] * req.Required_Per_Unit / (1 - yl)
    need = req.groupby("Material_ID")[mcols].sum().reindex(mat.index).fillna(0)
    rec = po[po.Order_Date > S.Order_Date.max() - pd.DateOffset(months=12)]
    lt = rec.groupby("Material_ID").agg(p90=("lead", lambda x: x.quantile(.9)), late=("on_time", lambda x: 1 - x.mean()), dwl=("delay", lambda x: x[x > 0].mean()))
    ue2 = S.groupby("Product_ID").agg(n=("Net_Sales_EGP", "sum"), g=("Gross_Profit_EGP", "sum"), q=("Quantity", "sum")); gpu = ue2.g / ue2.q
    bx = bom.assign(day=bom.Product_ID.map(fc.sum(axis=1) / 90) * bom.Product_ID.map(gpu)); gpday = bx.groupby("Material_ID").day.sum()
    rd = lt.join(gpday.rename("gp_per_day")).join(mat[["Material_Name", "Standard_Lead_Time_Days"]]).fillna({"gp_per_day": 0, "dwl": 0})
    rd["risk"] = rd.late * rd.dwl * rd.gp_per_day
    q75, q50 = rd.risk.quantile(.75), rd.risk.quantile(.5)
    rd["tier"] = np.where(rd.gp_per_day == 0, "n/a", np.where(rd.risk >= q75, "RED", np.where(rd.risk >= q50, "AMBER", "GREEN")))
    rd = rd.sort_values("risk", ascending=False).reset_index()
    cm = {"RED": RED, "AMBER": AMBER, "GREEN": GREEN, "n/a": "#8a93a6"}
    a, b = st.columns(2)
    show(px.bar(rd, y="Material_Name", x="risk", color="tier", color_discrete_map=cm, orientation="h", title="Expected gross profit at risk per late delivery (EGP)").update_yaxes(autorange="reversed"), a)
    show(px.scatter(rd[rd.gp_per_day > 0], x="late", y="gp_per_day", size="risk", color="tier", color_discrete_map=cm, hover_name="Material_Name", title="Chance of late delivery vs gross profit per day at stake"), b)
    st.markdown("**Enter raw-material stock on hand** (same unit as the BOM). The order quantity is the 90-day need minus stock on hand.")
    oh = st.data_editor(pd.DataFrame({"Material_ID": mat.index, "Material_Name": mat.Material_Name.values, "on_hand": 0.0}), disabled=["Material_ID", "Material_Name"], hide_index=True)
    cal = []
    for mid in need.index:
        if need.loc[mid].sum() <= 0: continue
        p90 = int(np.ceil(rd.set_index("Material_ID").loc[mid, "p90"])); std = int(mat.loc[mid, "Standard_Lead_Time_Days"])
        for mo in mcols:
            nb = mo - pd.Timedelta(days=cyc + hnd); ob = nb - pd.Timedelta(days=p90)
            cal.append({"Material": mat.loc[mid, "Material_Name"], "For month": mo.strftime("%b %Y"), "Need": round(need.loc[mid, mo]), "Need on site by": nb.date(), "Order by (risk-adjusted)": ob.date(),
                        "Order by (master data)": (nb - pd.Timedelta(days=std)).date(), "Status": "ORDER NOW" if ob.date() < asof else "Scheduled", "Tier": rd.set_index("Material_ID").loc[mid, "tier"]})
    cal = pd.DataFrame(cal); now = int((cal.Status == "ORDER NOW").sum())
    k = st.columns(3); k[0].metric("Order lines already inside lead time", f"{now} of {len(cal)}"); k[1].metric("Red-tier materials", int((rd.tier == "RED").sum())); k[2].metric("Radar lead-time p90 (avg days)", f"{rd.p90.mean():.1f}")
    st.dataframe(cal, hide_index=True); st.download_button("Download order calendar (CSV)", cal.to_csv(index=False), "order_calendar.csv")
    to_order = need.sum(axis=1).sub(oh.set_index("Material_ID").on_hand).clip(lower=0).round(); to_order = to_order[to_order > 0].rename("order_qty_90d").reset_index().merge(oh[["Material_ID", "Material_Name"]])
    st.dataframe(to_order, hide_index=True)
