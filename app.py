import streamlit as st
import psycopg2
import hashlib
from datetime import date, datetime
import pandas as pd
import plotly.express as px

# --- 1. PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Smart Finance Super App",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# --- 2. GLOBAL CSS (DARK EMERALD MOBILE THEME & NO SIDEBAR) ---
st.markdown("""
<style>
.stApp { background-color: #0b2521; color: #e0f2f1; }
[data-testid="collapsedControl"] { display: none !important; }
section[data-testid="stSidebar"] { display: none !important; }
header[data-testid="stHeader"] { background-color: transparent !important; }
[data-testid="stForm"] {
    background-color: #12332e !important;
    border-radius: 16px !important;
    border: 1px solid #1e5249 !important;
    padding: 20px !important;
}
.stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div, .stTextArea>div>div>textarea {
    background-color: #18423b !important;
    color: #ffffff !important;
    border-radius: 10px !important;
    border: 1px solid #277063 !important;
}
.stButton>button, .stFormSubmitButton>button {
    background: linear-gradient(135deg, #277063 0%, #1b5248 100%) !important;
    color: #ffffff !important;
    border-radius: 14px !important;
    border: 1px solid #328f7e !important;
    height: 52px !important;
    font-size: 16px !important;
    font-weight: 600 !important;
    transition: 0.2s ease-in-out;
}
.stButton>button:hover, .stFormSubmitButton>button:hover {
    background: linear-gradient(135deg, #328f7e 0%, #277063 100%) !important;
    border-color: #4ade80 !important;
}
h1, h2, h3, h4, h5, h6, p, label, span { color: #e0f2f1 !important; }
.custom-card {
    background: linear-gradient(135deg, #12332e 0%, #0d2622 100%);
    padding: 18px;
    border-radius: 16px;
    border: 1px solid #1e5249;
    margin-bottom: 12px;
}
.hero-card {
    background: linear-gradient(135deg, #154c43 0%, #0a2521 100%);
    padding: 24px;
    border-radius: 20px;
    border: 1px solid #2b7a6b;
    box-shadow: 0 6px 20px rgba(0,0,0,0.35);
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)

# --- 3. SAFE DATABASE ENGINE ---
def get_db_connection():
    if "CLOUD_DB_URL" not in st.secrets:
        st.error("❌ CLOUD_DB_URL is missing in Streamlit Secrets!")
        st.stop()
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"])

def run_query(query, params=(), fetch=False, fetchone=False):
    conn = get_db_connection()
    try:
        with conn.cursor() as c:
            c.execute(query, params)
            if fetchone:
                res = c.fetchone()
                conn.commit()
                return res
            if fetch:
                res = c.fetchall()
                conn.commit()
                return res
            conn.commit()
    finally:
        conn.close()

def fetch_df(query, params=()):
    conn = get_db_connection()
    try:
        return pd.read_sql_query(query, conn, params=params)
    finally:
        conn.close()

SECRET_SALT = st.secrets.get("SECRET_SALT", "CloudFinanceForce2026")

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SECRET_SALT.encode('utf-8'), 100000).hex()

# --- 4. AUTO DATABASE MIGRATION ---
@st.cache_resource
def init_cloud_db():
    try:
        queries = [
            """CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL,
                password_hash TEXT NOT NULL, role VARCHAR(20) NOT NULL DEFAULT 'user',
                status VARCHAR(20) NOT NULL DEFAULT 'active'
            );""",
            """CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                name VARCHAR(100) NOT NULL, type VARCHAR(50) NOT NULL, balance NUMERIC NOT NULL DEFAULT 0.0
            );""",
            """CREATE TABLE IF NOT EXISTS custom_assets (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                asset_name VARCHAR(100) NOT NULL, category VARCHAR(50) NOT NULL, estimated_value NUMERIC NOT NULL DEFAULT 0.0
            );""",
            """CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, tx_date DATE NOT NULL,
                tx_type VARCHAR(20) NOT NULL, category VARCHAR(50) NOT NULL, amount NUMERIC NOT NULL, description TEXT
            );""",
            """CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                title VARCHAR(100) NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE
            );""",
            """CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                category VARCHAR(50) NOT NULL, monthly_limit NUMERIC NOT NULL, year_month VARCHAR(7) NOT NULL,
                UNIQUE(user_id, category, year_month)
            );""",
            """CREATE TABLE IF NOT EXISTS savings_goals (
                id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                goal_name VARCHAR(100) NOT NULL, target_amount NUMERIC NOT NULL, current_amount NUMERIC NOT NULL DEFAULT 0.0
            );"""
        ]
        for q in queries:
            run_query(q)

        admin_hash = hash_password("admin123")
        run_query(
            "INSERT INTO users (username, password_hash, role, status) VALUES ('admin', %s, 'admin', 'active') ON CONFLICT (username) DO NOTHING;",
            (admin_hash,)
        )
    except Exception as e:
        st.error(f"DB Initialization Error: {e}")

init_cloud_db()

# --- 5. SESSION STATES ---
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "currency" not in st.session_state:
    st.session_state.currency = "KWD (د.ك)"

def go_to(page):
    st.session_state.current_page = page

# --- 6. AUTHENTICATION (LOGIN & SIGN UP) ---
if st.session_state.user is None:
    st.markdown("<h1 style='text-align: center; color: #4ade80; margin-top: 20px;'>💎 Finance Cloud Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #88aba6;'>Super Edition • Wealth & Asset Manager</p>", unsafe_allow_html=True)

    tab_login, tab_register = st.tabs(["🔐 Secure Login", "📝 Create Account"])

    with tab_login:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submit = st.form_submit_button("Login to Workspace", use_container_width=True)

        if submit:
            if not username or not password:
                st.warning("Please enter both username and password.")
            else:
                p_hash = hash_password(password)
                row = run_query(
                    "SELECT id, username, role, status FROM users WHERE username=%s AND password_hash=%s;",
                    (username.strip(), p_hash),
                    fetchone=True
                )
                if row:
                    if row[3] == 'inactive':
                        st.error("❌ Your account is INACTIVE. Contact Administrator.")
                    else:
                        st.session_state.user = {"id": row[0], "username": row[1], "role": row[2]}
                        acc_cnt = run_query("SELECT COUNT(*) FROM accounts WHERE user_id=%s;", (row[0],), fetchone=True)[0]
                        if acc_cnt == 0:
                            run_query(
                                "INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Main Bank', 'Bank', 0.0), (%s, 'Cash Wallet', 'Cash', 0.0);",
                                (row[0], row[0])
                            )
                        st.rerun()
                else:
                    st.error("❌ Invalid Username or Password!")

    with tab_register:
        with st.form("register_form"):
            new_u = st.text_input("Choose Username")
            new_p = st.text_input("Choose Password", type="password")
            conf_p = st.text_input("Confirm Password", type="password")
            reg_btn = st.form_submit_button("Create Free Account", use_container_width=True)

        if reg_btn:
            if not new_u.strip() or not new_p:
                st.warning("All fields are required!")
            elif new_p != conf_p:
                st.error("Passwords do not match!")
            else:
                try:
                    p_hash = hash_password(new_p)
                    run_query(
                        "INSERT INTO users (username, password_hash, role, status) VALUES (%s, %s, 'user', 'active');",
                        (new_u.strip(), p_hash)
                    )
                    st.success("✅ Account created! Please switch to the Login tab to sign in.")
                except Exception:
                    st.error("❌ Username already exists! Try another one.")

# --- 7. MAIN SUPER APP WORKSPACE ---
else:
    uid = st.session_state.user['id']
    uname = st.session_state.user['username'].capitalize()
    curr = st.session_state.currency.split()[0]

    # Global Top Navigation Bar for Sub-pages
    if st.session_state.current_page != "Home":
        if st.button("⬅️ Back to Home Menu", use_container_width=True):
            go_to("Home")
            st.rerun()
        st.markdown("<hr style='border-color: #1e5249; margin: 10px 0 20px 0;'>", unsafe_allow_html=True)

    # ================= HOME SCREEN =================
    if st.session_state.current_page == "Home":
        # Quick Summary Calculations
        bank_bal = float(run_query("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE user_id=%s;", (uid,), fetchone=True)[0])
        asset_val = float(run_query("SELECT COALESCE(SUM(estimated_value), 0) FROM custom_assets WHERE user_id=%s;", (uid,), fetchone=True)[0])
        unread_cnt = int(run_query("SELECT COUNT(*) FROM notifications WHERE user_id=%s AND is_read=FALSE;", (uid,), fetchone=True)[0])
        net_worth = bank_bal + asset_val

        # Header & Currency
        col_top1, col_top2 = st.columns([2, 1])
        with col_top1:
            st.markdown(f"<h2 style='margin-bottom:0;'>Hello, {uname} 👋</h2>", unsafe_allow_html=True)
            st.markdown("<p style='color:#88aba6; margin-top:2px;'>Welcome to your financial hub</p>", unsafe_allow_html=True)
        with col_top2:
            curr_list = ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"]
            new_curr = st.selectbox("💱 Currency", curr_list, index=curr_list.index(st.session_state.currency))
            if new_curr != st.session_state.currency:
                st.session_state.currency = new_curr
                st.rerun()

        # Hero Net Worth Banner on Home
        st.markdown(f"""<div class="hero-card">
<p style="margin:0; color:#88aba6; font-size:14px;">💎 TOTAL NET WORTH</p>
<h1 style="margin:4px 0 12px 0; color:#4ade80; font-size:34px;">{curr} {net_worth:,.2f}</h1>
<div style="display:flex; justify-content:space-between; border-top:1px solid #1e5249; padding-top:10px;">
<span>🏦 Cash & Banks: <b>{curr} {bank_bal:,.2f}</b></span>
<span>🏠 Assets: <b>{curr} {asset_val:,.2f}</b></span>
</div>
</div>""", unsafe_allow_html=True)

        st.markdown("### 🧭 Quick Actions")

        # 2-Column Mobile Button Grid
        c1, c2 = st.columns(2)
        with c1:
            if st.button("📊 Analytics & Charts", use_container_width=True):
                go_to("Dashboard")
                st.rerun()
            if st.button("💸 Transactions", use_container_width=True):
                go_to("Transactions")
                st.rerun()
            if st.button("🏠 Custom Assets", use_container_width=True):
                go_to("Assets")
                st.rerun()
            inbox_label = f"🔔 Inbox ({unread_cnt} New)" if unread_cnt > 0 else "🔔 Inbox"
            if st.button(inbox_label, use_container_width=True):
                go_to("Inbox")
                st.rerun()

        with c2:
            if st.button("💳 My Wallet & Cards", use_container_width=True):
                go_to("Wallet")
                st.rerun()
            if st.button("🏦 Money Transfer", use_container_width=True):
                go_to("Transfer")
                st.rerun()
            if st.button("🎯 Budgets & Goals", use_container_width=True):
                go_to("Budgets")
                st.rerun()
            if st.button("⚙️ Profile & Security", use_container_width=True):
                go_to("Profile")
                st.rerun()

        if st.session_state.user['role'] == 'admin':
            st.markdown("<hr style='border-color: #1e5249;'>", unsafe_allow_html=True)
            if st.button("🔑 Master Admin Control Panel", use_container_width=True):
                go_to("Admin")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout Safely", use_container_width=True):
            st.session_state.user = None
            go_to("Home")
            st.rerun()

    # ================= 1. ANALYTICS DASHBOARD =================
    elif st.session_state.current_page == "Dashboard":
        st.title("📊 Financial Analytics")

        bank_bal = float(run_query("SELECT COALESCE(SUM(balance), 0) FROM accounts WHERE user_id=%s;", (uid,), fetchone=True)[0])
        asset_val = float(run_query("SELECT COALESCE(SUM(estimated_value), 0) FROM custom_assets WHERE user_id=%s;", (uid,), fetchone=True)[0])
        tot_inc = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Income';", (uid,), fetchone=True)[0])
        tot_exp = float(run_query("SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE user_id=%s AND tx_type='Expense';", (uid,), fetchone=True)[0])

        st.markdown(f"""<div style="display:grid; grid-template-columns:1fr 1fr; gap:12px; margin-bottom:15px;">
<div class="custom-card">
<p style="margin:0; color:#88aba6; font-size:13px;">📈 Total Income</p>
<h3 style="margin:4px 0 0 0; color:#4ade80;">{curr} {tot_inc:,.2f}</h3>
</div>
<div class="custom-card">
<p style="margin:0; color:#88aba6; font-size:13px;">📉 Total Expenses</p>
<h3 style="margin:4px 0 0 0; color:#f87171;">{curr} {tot_exp:,.2f}</h3>
</div>
</div>""", unsafe_allow_html=True)

        tx_df = fetch_df("SELECT tx_date, tx_type, category, amount FROM transactions WHERE user_id=%s", (uid,))

        if not tx_df.empty:
            col_c1, col_c2 = st.columns(2)
            with col_c1:
                st.subheader("Expense Breakdown")
                exp_df = tx_df[tx_df['tx_type'] == 'Expense']
                if not exp_df.empty:
                    fig_pie = px.pie(exp_df, values='amount', names='category', hole=0.5, color_discrete_sequence=px.colors.sequential.Tealgrn)
                    fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0f2f1'))
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No expenses recorded yet.")

            with col_c2:
                st.subheader("Monthly Cashflow")
                tx_df['Month'] = pd.to_datetime(tx_df['tx_date']).dt.strftime('%Y-%m')
                trend_df = tx_df.groupby(['Month', 'tx_type'])['amount'].sum().reset_index()
                fig_bar = px.bar(trend_df, x='Month', y='amount', color='tx_type', barmode='group', color_discrete_map={'Income': '#4ade80', 'Expense': '#f87171'})
                fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0f2f1'))
                st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("💡 Add transactions to unlock visual analytics!")

    # ================= 2. MY WALLET & CARDS =================
    elif st.session_state.current_page == "Wallet":
        st.title("💳 My Wallet & Accounts")

        accs = run_query("SELECT id, name, type, balance FROM accounts WHERE user_id=%s ORDER BY id ASC;", (uid,), fetch=True)
        if accs:
            for a_id, a_name, a_type, a_bal in accs:
                st.markdown(f"""<div class="custom-card" style="display:flex; justify-content:space-between; align-items:center;">
<div>
<span style="background:#277063; padding:3px 10px; border-radius:8px; font-size:12px;">{a_type}</span>
<h3 style="margin:6px 0 0 0;">{a_name}</h3>
</div>
<div style="text-align:right;">
<p style="margin:0; color:#88aba6; font-size:12px;">Available Balance</p>
<h3 style="margin:4px 0 0 0; color:#4ade80;">{curr} {float(a_bal):,.2f}</h3>
</div>
</div>""", unsafe_allow_html=True)

        st.subheader("➕ Add New Card / Bank Account")
        with st.form("add_acc_form"):
            acc_name = st.text_input("Account or Card Name (e.g., Visa **** 2400, NBK Bank)")
            acc_type = st.selectbox("Type", ["Bank", "Visa Card", "Mastercard", "Cash Wallet", "Savings", "Crypto Wallet"])
            init_bal = st.number_input("Opening Balance", value=0.0, step=10.0)
            btn_acc = st.form_submit_button("Add to Wallet", use_container_width=True)

        if btn_acc and acc_name.strip():
            run_query("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, %s, %s, %s);", (uid, acc_name.strip(), acc_type, init_bal))
            st.success("✅ Account added to wallet!")
            st.rerun()

    # ================= 3. TRANSACTIONS =================
    elif st.session_state.current_page == "Transactions":
        st.title("💸 Smart Transactions")

        acc_df = fetch_df("SELECT id, name, balance FROM accounts WHERE user_id=%s ORDER BY id ASC", (uid,))
        acc_map = {f"{r['name']} ({curr} {float(r['balance']):,.2f})": r['id'] for _, r in acc_df.iterrows()}

        with st.form("tx_form"):
            tx_type = st.selectbox("Transaction Type", ["Expense", "Income"])
            sel_acc_label = st.selectbox("Select Account", list(acc_map.keys()) if acc_map else ["No Accounts"])
            cat = st.selectbox("Category", ["Food & Dining", "Groceries", "Rent & Utilities", "Salary", "Transport", "Shopping", "Entertainment", "Healthcare", "Investments", "Other"])
            tx_amt = st.number_input("Amount", min_value=0.01, step=5.0)
            tx_date = st.date_input("Date", value=date.today())
            tx_desc = st.text_input("Description / Notes")
            btn_tx = st.form_submit_button("Record Transaction", use_container_width=True)

        if btn_tx and acc_map:
            acc_id = acc_map[sel_acc_label]
            run_query(
                "INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) VALUES (%s, %s, %s, %s, %s, %s, %s);",
                (uid, acc_id, tx_date, tx_type, cat, tx_amt, tx_desc)
            )
            bal_diff = tx_amt if tx_type == "Income" else -tx_amt
            run_query("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (bal_diff, acc_id))
            st.success("✅ Transaction recorded & balance updated!")
            st.rerun()

        st.subheader("📋 Recent Transactions")
        tx_hist = fetch_df("""
            SELECT t.id as "ID", t.tx_date as "Date", a.name as "Account", t.tx_type as "Type",
                   t.category as "Category", t.amount as "Amount", t.description as "Notes"
            FROM transactions t JOIN accounts a ON t.account_id = a.id
            WHERE t.user_id=%s ORDER BY t.tx_date DESC, t.id DESC LIMIT 50
        """, (uid,))

        if not tx_hist.empty:
            csv_data = tx_hist.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Export History to CSV", data=csv_data, file_name="transactions.csv", mime="text/csv", use_container_width=True)

            display_df = tx_hist.copy()
            display_df["Amount"] = display_df["Amount"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(display_df, use_container_width=True, hide_index=True)

            with st.expander("🗑️ Delete / Revert a Transaction"):
                del_id = st.selectbox("Select Transaction ID to Delete", tx_hist["ID"].tolist())
                if st.button("Delete & Reverse Balance", use_container_width=True):
                    tx_row = run_query("SELECT account_id, tx_type, amount FROM transactions WHERE id=%s AND user_id=%s;", (del_id, uid), fetchone=True)
                    if tx_row:
                        rev_diff = -float(tx_row[2]) if tx_row[1] == "Income" else float(tx_row[2])
                        run_query("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (rev_diff, tx_row[0]))
                        run_query("DELETE FROM transactions WHERE id=%s AND user_id=%s;", (del_id, uid))
                        st.success("Transaction deleted and account balance restored!")
                        st.rerun()
        else:
            st.info("No transactions recorded yet.")

    # ================= 4. MONEY TRANSFER =================
    elif st.session_state.current_page == "Transfer":
        st.title("🏦 Account-to-Account Transfer")
        accs = fetch_df("SELECT id, name, balance FROM accounts WHERE user_id=%s", (uid,))

        if len(accs) >= 2:
            with st.form("trf_form"):
                f_acc = st.selectbox("From Account (Origin)", accs['name'].tolist(), index=0)
                t_acc = st.selectbox("To Account (Destination)", accs['name'].tolist(), index=1)
                amt = st.number_input("Transfer Amount", min_value=0.01, step=10.0)
                btn_trf = st.form_submit_button("Execute Instant Transfer", use_container_width=True)

            if btn_trf:
                if f_acc == t_acc:
                    st.error("❌ Origin and Destination accounts must be different!")
                else:
                    run_query("UPDATE accounts SET balance = balance - %s WHERE name=%s AND user_id=%s;", (amt, f_acc, uid))
                    run_query("UPDATE accounts SET balance = balance + %s WHERE name=%s AND user_id=%s;", (amt, t_acc, uid))
                    st.success(f"✅ Transferred {curr} {amt:,.2f} from {f_acc} to {t_acc}!")
                    st.rerun()
        else:
            st.warning("⚠️ Please create at least 2 accounts in 'My Wallet' to transfer funds.")

    # ================= 5. CUSTOM ASSETS =================
    elif st.session_state.current_page == "Assets":
        st.title("🏠 Property & Asset Portfolio")

        with st.form("asset_form"):
            a_name = st.text_input("Asset Name (e.g., Gold Bars, Apartment, Land)")
            a_cat = st.selectbox("Asset Category", ["Real Estate", "Gold & Jewelry", "Vehicles", "Stocks & Bonds", "Crypto", "Business Equity"])
            a_val = st.number_input("Current Estimated Value", min_value=0.0, step=100.0)
            btn_ast = st.form_submit_button("Add Asset to Net Worth", use_container_width=True)

        if btn_ast and a_name.strip():
            run_query("INSERT INTO custom_assets (user_id, asset_name, category, estimated_value) VALUES (%s, %s, %s, %s);", (uid, a_name.strip(), a_cat, a_val))
            st.success("✅ Asset added!")
            st.rerun()

        df_assets = fetch_df("SELECT id as \"ID\", asset_name as \"Asset\", category as \"Category\", estimated_value as \"Value\" FROM custom_assets WHERE user_id=%s", (uid,))
        if not df_assets.empty:
            disp_ast = df_assets.copy()
            disp_ast["Value"] = disp_ast["Value"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(disp_ast, use_container_width=True, hide_index=True)

            with st.expander("🗑️ Remove an Asset"):
                del_ast = st.selectbox("Select Asset ID", df_assets["ID"].tolist())
                if st.button("Delete Asset", use_container_width=True):
                    run_query("DELETE FROM custom_assets WHERE id=%s AND user_id=%s;", (del_ast, uid))
                    st.success("Asset removed!")
                    st.rerun()

    # ================= 6. BUDGETS & SAVINGS GOALS =================
    elif st.session_state.current_page == "Budgets":
        st.title("🎯 Budgets & Savings Goals")
        tab_goals, tab_budgets = st.tabs(["🚀 Savings Goals", "📊 Monthly Expense Budgets"])

        with tab_goals:
            st.subheader("Your Financial Goals")
            goals = run_query("SELECT id, goal_name, target_amount, current_amount FROM savings_goals WHERE user_id=%s ORDER BY id ASC;", (uid,), fetch=True)
            if goals:
                for g_id, g_name, g_target, g_curr in goals:
                    pct = min(float(g_curr) / float(g_target) * 100, 100.0) if float(g_target) > 0 else 0.0
                    st.markdown(f"""<div class="custom-card">
<div style="display:flex; justify-content:space-between;">
<b>🎯 {g_name}</b>
<span style="color:#4ade80;">{pct:.1f}%</span>
</div>
<p style="margin:4px 0; font-size:13px; color:#88aba6;">{curr} {float(g_curr):,.2f} / {curr} {float(g_target):,.2f}</p>
</div>""", unsafe_allow_html=True)
                    st.progress(min(float(g_curr) / float(g_target), 1.0))

            with st.expander("➕ Create New Goal"):
                with st.form("new_goal_form"):
                    g_title = st.text_input("Goal Title (e.g., Tesla Model S, Emergency Fund)")
                    g_targ = st.number_input("Target Amount", min_value=10.0, step=100.0)
                    g_init = st.number_input("Initial Saved Amount", min_value=0.0, step=50.0)
                    if st.form_submit_button("Create Goal", use_container_width=True) and g_title.strip():
                        run_query("INSERT INTO savings_goals (user_id, goal_name, target_amount, current_amount) VALUES (%s, %s, %s, %s);", (uid, g_title.strip(), g_targ, g_init))
                        st.success("Goal created!")
                        st.rerun()

            if goals:
                with st.expander("💰 Deposit Money into a Goal"):
                    with st.form("add_goal_funds"):
                        goal_dict = {g[1]: g[0] for g in goals}
                        sel_g = st.selectbox("Select Goal", list(goal_dict.keys()))
                        add_val = st.number_input("Amount to Add", min_value=1.0, step=20.0)
                        if st.form_submit_button("Update Goal Progress", use_container_width=True):
                            run_query("UPDATE savings_goals SET current_amount = current_amount + %s WHERE id=%s;", (add_val, goal_dict[sel_g]))
                            st.success("Goal progress updated!")
                            st.rerun()

        with tab_budgets:
            curr_month = datetime.now().strftime("%Y-%m")
            with st.form("budget_form"):
                b_cat = st.selectbox("Category", ["Food & Dining", "Groceries", "Rent & Utilities", "Transport", "Shopping", "Entertainment"])
                b_limit = st.number_input("Monthly Spending Limit", min_value=1.0, step=25.0)
                if st.form_submit_button("Save Monthly Limit", use_container_width=True):
                    run_query(
                        "INSERT INTO budgets (user_id, category, monthly_limit, year_month) VALUES (%s, %s, %s, %s) ON CONFLICT(user_id, category, year_month) DO UPDATE SET monthly_limit=EXCLUDED.monthly_limit;",
                        (uid, b_cat, b_limit, curr_month)
                    )
                    st.success("Budget updated!")
                    st.rerun()

            budgets = fetch_df("SELECT category, monthly_limit FROM budgets WHERE user_id=%s AND year_month=%s", (uid, curr_month))
            tx_spent = fetch_df("SELECT category, SUM(amount) as spent FROM transactions WHERE user_id=%s AND tx_type='Expense' AND TO_CHAR(tx_date, 'YYYY-MM')=%s GROUP BY category", (uid, curr_month))

            if not budgets.empty:
                for _, r in budgets.iterrows():
                    cat, limit = r['category'], float(r['monthly_limit'])
                    spent_row = tx_spent[tx_spent['category'] == cat]
                    spent = float(spent_row['spent'].values[0]) if not spent_row.empty else 0.0
                    st.write(f"**{cat}** — Spent: {curr} {spent:,.2f} / Limit: {curr} {limit:,.2f}")
                    st.progress(min(spent / limit, 1.0))

    # ================= 7. INBOX =================
    elif st.session_state.current_page == "Inbox":
        st.title("🔔 Notifications Inbox")
        run_query("UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND is_read=FALSE;", (uid,))
        notifs = run_query("SELECT title, message, created_at FROM notifications WHERE user_id=%s ORDER BY created_at DESC;", (uid,), fetch=True)

        if notifs:
            for n_title, n_msg, n_date in notifs:
                st.markdown(f"""<div class="custom-card">
<div style="display:flex; justify-content:space-between;">
<b style="color:#4ade80;">📢 {n_title}</b>
<span style="font-size:12px; color:#88aba6;">{str(n_date)[:16]}</span>
</div>
<p style="margin:8px 0 0 0;">{n_msg}</p>
</div>""", unsafe_allow_html=True)
        else:
            st.info("Your inbox is empty.")

    # ================= 8. PROFILE & SECURITY =================
    elif st.session_state.current_page == "Profile":
        st.title("⚙️ Profile & Security")
        st.write(f"**Logged in as:** `{st.session_state.user['username']}` | **Role:** `{st.session_state.user['role'].upper()}`")

        with st.form("pwd_form"):
            st.subheader("🔒 Change Password")
            new_pass = st.text_input("New Password", type="password")
            conf_pass = st.text_input("Confirm New Password", type="password")
            if st.form_submit_button("Update Password", use_container_width=True):
                if not new_pass or new_pass != conf_pass:
                    st.error("Passwords must match and cannot be empty!")
                else:
                    run_query("UPDATE users SET password_hash=%s WHERE id=%s;", (hash_password(new_pass), uid))
                    st.success("✅ Password updated successfully!")

    # ================= 9. ADMIN PANEL =================
    elif st.session_state.current_page == "Admin" and st.session_state.user['role'] == 'admin':
        st.title("🔑 Master Admin Control Panel")
        users_df = fetch_df("SELECT id as \"ID\", username as \"User\", role as \"Role\", status as \"Status\" FROM users ORDER BY id ASC")
        st.dataframe(users_df, use_container_width=True, hide_index=True)

        other_users = users_df[users_df['User'] != 'admin']['User'].tolist()
        if other_users:
            with st.form("admin_user_form"):
                sel_u = st.selectbox("Select User to Activate / Deactivate", other_users)
                if st.form_submit_button("Toggle User Access Status", use_container_width=True):
                    curr_s = run_query("SELECT status FROM users WHERE username=%s;", (sel_u,), fetchone=True)[0]
                    nxt_s = 'inactive' if curr_s == 'active' else 'active'
                    run_query("UPDATE users SET status=%s WHERE username=%s;", (nxt_s, sel_u))
                    st.success(f"User '{sel_u}' is now {nxt_s.upper()}!")
                    st.rerun()

        st.subheader("📡 Send Broadcast Alert")
        with st.form("bcast_form"):
            b_title = st.text_input("Broadcast Title")
            b_msg = st.text_area("Message Content")
            if st.form_submit_button("Send to All Users", use_container_width=True) and b_title.strip():
                all_u = run_query("SELECT id FROM users;", fetch=True)
                for u_row in all_u:
                    run_query("INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s);", (u_row[0], b_title.strip(), b_msg.strip()))
                st.success("✅ Broadcast sent to all users!")
