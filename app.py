import streamlit as st
import psycopg2
import hashlib
from datetime import date, datetime
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION & MODERN UI SETUP ---
st.set_page_config(page_title="Smart Finance Enterprise", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

# Apply Modern Dark Green Theme & Hide Sidebar Toggle
st.markdown("""
<style>
    /* Main Background */
    .stApp {
        background-color: #0b2521;
        color: #e0f2f1;
    }
    
    /* Hide Sidebar Toggle Completely */
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* Cards / Forms Background */
    .st-emotion-cache-1wivap2, [data-testid="stForm"] {
        background-color: #12332e !important;
        border-radius: 15px !important;
        border: 1px solid #1e5249 !important;
        padding: 20px;
    }

    /* Input Fields */
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1e5249 !important;
        color: white !important;
        border-radius: 10px !important;
        border: none !important;
    }

    /* Buttons */
    .stButton>button, .stFormSubmitButton>button {
        background-color: #277063 !important;
        color: white !important;
        border-radius: 12px !important;
        border: none !important;
        transition: 0.3s;
        padding: 15px !important;
        font-size: 16px !important;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover {
        background-color: #328f7e !important;
    }

    /* Text Colors */
    h1, h2, h3, h4, h5, h6, p, label {
        color: #e0f2f1 !important;
    }
    
    /* Dataframes */
    .stDataFrame {
        background-color: #12332e;
        border-radius: 10px;
    }
    
    /* Hide Default Header Elements */
    header[data-testid="stHeader"] {
        background-color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

def get_db_connection():
    if "CLOUD_DB_URL" not in st.secrets:
        st.error("❌ CLOUD_DB_URL is missing in st.secrets!")
        st.stop()
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"])

SECRET_SALT = st.secrets.get("SECRET_SALT", "CloudFinanceForce2026")

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SECRET_SALT.encode('utf-8'), 100000).hex()

# --- 2. DATABASE AUTO-MIGRATION ---
@st.cache_resource
def init_cloud_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()

        tables = [
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
            );"""
        ]
        
        for query in tables:
            c.execute(query)

        # Default Master Admin
        admin_hash = hash_password("admin123")
        c.execute("INSERT INTO users (username, password_hash, role, status) VALUES ('admin', %s, 'admin', 'active') ON CONFLICT (username) DO NOTHING;", (admin_hash,))
        
        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        st.error(f"Database Error: {e}")

init_cloud_db()

# Initialize Session States
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "currency" not in st.session_state:
    st.session_state.currency = "KWD (د.ك)"

# --- 3. AUTHENTICATION (LOGIN) ---
if st.session_state.user is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.markdown("<h1 style='text-align: center; color: #4ade80;'>💎 Finance Cloud</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: #a3c9c2;'>Executive Wealth Manager</p>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            submit = st.form_submit_button("Secure Login", use_container_width=True)

            if submit:
                p_hash = hash_password(password)
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("SELECT id, username, role, status FROM users WHERE username=%s AND password_hash=%s;", (username.strip(), p_hash))
                row = c.fetchone()
                c.close()
                conn.close()

                if row:
                    uid, uname, role, status = row
                    if status == 'inactive':
                        st.error("❌ Account is INACTIVE. Please contact System Administrator.")
                    else:
                        st.session_state.user = {"id": uid, "username": uname, "role": role}
                        
                        # Default Accounts Setup
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("SELECT COUNT(*) FROM accounts WHERE user_id=%s;", (uid,))
                        if c.fetchone()[0] == 0:
                            c.execute("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Main Bank', 'Bank', 0.0), (%s, 'Cash Wallet', 'Cash', 0.0);", (uid, uid))
                            conn.commit()
                        c.close()
                        conn.close()
                        st.rerun()
                else:
                    st.error("Invalid Credentials!")

# --- 4. MAIN APPLICATION WORKSPACE ---
else:
    uid = st.session_state.user['id']
    curr = st.session_state.currency.split()[0]
    
    # Back Button Logic for Sub-pages
    if st.session_state.current_page != "Home":
        if st.button("⬅️ Back to Home", use_container_width=True):
            st.session_state.current_page = "Home"
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)

    # --- HOME NAVIGATION SCREEN ---
    if st.session_state.current_page == "Home":
        st.markdown(f"<h2 style='color:#4ade80;'>Hello 👤 {st.session_state.user['username'].capitalize()}</h2>", unsafe_allow_html=True)
        
        # Currency Selector
        new_curr = st.selectbox("💱 Active Currency", ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"], index=["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"].index(st.session_state.currency))
        if new_curr != st.session_state.currency:
            st.session_state.currency = new_curr
            st.rerun()

        st.markdown("<br>### 🧭 Navigation Menu", unsafe_allow_html=True)
        
        # Action Buttons
        if st.button("📊 Executive Dashboard", use_container_width=True):
            st.session_state.current_page = "Dashboard"
            st.rerun()
            
        if st.button("🏠 Asset Portfolio", use_container_width=True):
            st.session_state.current_page = "Assets"
            st.rerun()
            
        if st.button("💸 Transactions", use_container_width=True):
            st.session_state.current_page = "Transactions"
            st.rerun()
            
        if st.button("🏦 Money Transfer", use_container_width=True):
            st.session_state.current_page = "Transfer"
            st.rerun()
            
        if st.button("🎯 Budgets & Goals", use_container_width=True):
            st.session_state.current_page = "Budgets"
            st.rerun()
            
        if st.button("🔔 Inbox / Notifications", use_container_width=True):
            st.session_state.current_page = "Inbox"
            st.rerun()
            
        if st.session_state.user['role'] == 'admin':
            if st.button("🔑 Admin Control Panel", use_container_width=True):
                st.session_state.current_page = "Admin"
                st.rerun()

        st.markdown("<br><br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            st.session_state.current_page = "Home"
            st.rerun()

    # --- MODULE 1: EXECUTIVE DASHBOARD ---
    elif st.session_state.current_page == "Dashboard":
        st.markdown("<h2 style='margin-bottom: 20px;'>📊 Analytics</h2>", unsafe_allow_html=True)
        
        conn = get_db_connection()
        
        c = conn.cursor()
        c.execute("SELECT SUM(balance) FROM accounts WHERE user_id=%s;", (uid,))
        bank_bal = float(c.fetchone()[0] or 0.0)

        c.execute("SELECT SUM(estimated_value) FROM custom_assets WHERE user_id=%s;", (uid,))
        asset_val = float(c.fetchone()[0] or 0.0)
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=%s AND tx_type='Expense';", (uid,))
        tot_exp = float(c.fetchone()[0] or 0.0)

        net_worth = bank_bal + asset_val

        # CUSTOM UI CARDS
        st.markdown(f"""
        <div style="display: flex; flex-direction: column; gap: 15px; margin-bottom: 25px;">
            <div style="background: linear-gradient(135deg, #0f3d36 0%, #0a2521 100%); padding: 25px; border-radius: 20px; box-shadow: 0 4px 15px rgba(0,0,0,0.3); border: 1px solid #1e5249;">
                <p style="color: #88aba6; font-size: 14px; margin: 0; font-weight: 500;">💎 Total Net Worth</p>
                <h1 style="color: #e0f2f1; font-size: 36px; margin: 5px 0 0 0; font-weight: bold;">{curr} {net_worth:,.2f}</h1>
            </div>
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px;">
                <div style="background-color: #12332e; padding: 20px; border-radius: 15px; border: 1px solid #1e5249;">
                    <p style="color: #88aba6; font-size: 13px; margin: 0;">🏦 Bank Balances</p>
                    <h3 style="color: #e0f2f1; font-size: 20px; margin: 5px 0 0 0;">{curr} {bank_bal:,.2f}</h3>
                </div>
                <div style="background-color: #12332e; padding: 20px; border-radius: 15px; border: 1px solid #1e5249;">
                    <p style="color: #88aba6; font-size: 13px; margin: 0;">🏠 Property & Assets</p>
                    <h3 style="color: #e0f2f1; font-size: 20px; margin: 5px 0 0 0;">{curr} {asset_val:,.2f}</h3>
                </div>
            </div>
            <div style="background-color: #12332e; padding: 20px; border-radius: 15px; border: 1px solid #1e5249; margin-top: 5px;">
                <p style="color: #f87171; font-size: 13px; margin: 0;">📉 Lifetime Expenses</p>
                <h3 style="color: #e0f2f1; font-size: 20px; margin: 5px 0 0 0;">{curr} {tot_exp:,.2f}</h3>
            </div>
        </div>
        """, unsafe_allow_html=True)

        tx_df = pd.read_sql_query("SELECT tx_date, tx_type, category, amount FROM transactions WHERE user_id=%s", conn, params=(uid,))
        conn.close()

        if not tx_df.empty:
            st.markdown("<h4 style='margin-top: 20px;'>Financial Dynamics</h4>", unsafe_allow_html=True)
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                exp_df = tx_df[tx_df['tx_type'] == 'Expense']
                if not exp_df.empty:
                    fig_pie = px.pie(exp_df, values='amount', names='category', hole=0.5, color_discrete_sequence=px.colors.sequential.Mint)
                    fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0f2f1'), showlegend=False)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No expense data for chart.")

            with col_chart2:
                tx_df['Month'] = pd.to_datetime(tx_df['tx_date']).dt.strftime('%Y-%m')
                trend_df = tx_df.groupby(['Month', 'tx_type'])['amount'].sum().reset_index()
                if not trend_df.empty:
                    fig_bar = px.bar(trend_df, x='Month', y='amount', color='tx_type', barmode='group', color_discrete_map={'Income':'#4ade80', 'Expense':'#f87171'})
                    fig_bar.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0f2f1'), legend=dict(title=""))
                    st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("💡 Record transactions to unlock AI-powered financial charts!")

    # --- MODULE 2: ASSET PORTFOLIO ---
    elif st.session_state.current_page == "Assets":
        st.title("🏠 Custom Assets")
        
        with st.form("asset_form"):
            a_name = st.text_input("Asset Name (e.g., Land)")
            a_cat = st.selectbox("Asset Class", ["Real Estate", "Gold", "Vehicles", "Stocks", "Crypto", "Business"])
            a_val = st.number_input("Estimated Market Value", min_value=0.0, step=100.0, format="%.2f")
            if st.form_submit_button("Save Asset", use_container_width=True) and a_name:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO custom_assets (user_id, asset_name, category, estimated_value) VALUES (%s, %s, %s, %s);", (uid, a_name, a_cat, a_val))
                conn.commit()
                c.close()
                conn.close()
                st.success("Asset successfully secured!")
                st.rerun()

        conn = get_db_connection()
        df_assets = pd.read_sql_query("SELECT id, asset_name as \"Asset\", category as \"Class\", estimated_value as \"Value\" FROM custom_assets WHERE user_id=%s", conn, params=(uid,))
        conn.close()
        
        if not df_assets.empty:
            df_assets["Value"] = df_assets["Value"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(df_assets, use_container_width=True, hide_index=True)

    # --- MODULE 3: TRANSACTIONS ---
    elif st.session_state.current_page == "Transactions":
        st.title("💸 Transactions")
        
        conn = get_db_connection()
        acc_df = pd.read_sql_query("SELECT id, name FROM accounts WHERE user_id=%s", conn, params=(uid,))
        acc_dict = dict(zip(acc_df['name'], acc_df['id'])) if not acc_df.empty else {}
        
        with st.form("tx_form"):
            tx_type = st.selectbox("Transaction Flow", ["Expense", "Income"])
            acc_name = st.selectbox("Account", list(acc_dict.keys()) if acc_dict else ["No Accounts Found"])
            cat = st
