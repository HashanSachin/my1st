import streamlit as st
import psycopg2
import hashlib
from datetime import date, datetime
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION ---
st.set_page_config(page_title="Smart Finance Enterprise", page_icon="💎", layout="wide", initial_sidebar_state="collapsed")

# Safe CSS for Dark Green Theme (No breaking elements)
st.markdown("""
<style>
    .stApp { background-color: #0b2521; color: #e0f2f1; }
    .st-emotion-cache-1wivap2, [data-testid="stForm"] {
        background-color: #12332e !important; border-radius: 15px !important;
        border: 1px solid #1e5249 !important; padding: 20px;
    }
    .stTextInput>div>div>input, .stNumberInput>div>div>input, .stSelectbox>div>div>div {
        background-color: #1e5249 !important; color: white !important;
        border-radius: 10px !important; border: none !important;
    }
    .stButton>button, .stFormSubmitButton>button {
        background-color: #277063 !important; color: white !important;
        border-radius: 12px !important; border: none !important; transition: 0.3s;
        height: 50px !important; font-size: 16px !important; font-weight: bold !important;
    }
    .stButton>button:hover, .stFormSubmitButton>button:hover { background-color: #328f7e !important; }
    h1, h2, h3, h4, p, label { color: #e0f2f1 !important; }
</style>
""", unsafe_allow_html=True)

# --- 2. DATABASE HELPER ---
def get_db_connection():
    if "CLOUD_DB_URL" not in st.secrets:
        st.error("❌ CLOUD_DB_URL is missing in .streamlit/secrets.toml!")
        st.stop()
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"])

SECRET_SALT = st.secrets.get("SECRET_SALT", "CloudFinanceForce2026")

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), SECRET_SALT.encode('utf-8'), 100000).hex()

@st.cache_resource
def init_cloud_db():
    try:
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("""CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password_hash TEXT NOT NULL, role VARCHAR(20) NOT NULL DEFAULT 'user', status VARCHAR(20) NOT NULL DEFAULT 'active');""")
        c.execute("""CREATE TABLE IF NOT EXISTS accounts (id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, type VARCHAR(50) NOT NULL, balance NUMERIC NOT NULL DEFAULT 0.0);""")
        c.execute("""CREATE TABLE IF NOT EXISTS custom_assets (id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, asset_name VARCHAR(100) NOT NULL, category VARCHAR(50) NOT NULL, estimated_value NUMERIC NOT NULL DEFAULT 0.0);""")
        c.execute("""CREATE TABLE IF NOT EXISTS transactions (id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, tx_date DATE NOT NULL, tx_type VARCHAR(20) NOT NULL, category VARCHAR(50) NOT NULL, amount NUMERIC NOT NULL, description TEXT);""")
        c.execute("""CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, title VARCHAR(100) NOT NULL, message TEXT NOT NULL, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, is_read BOOLEAN DEFAULT FALSE);""")
        c.execute("""CREATE TABLE IF NOT EXISTS budgets (id SERIAL PRIMARY KEY, user_id INT NOT NULL REFERENCES users(id) ON DELETE CASCADE, category VARCHAR(50) NOT NULL, monthly_limit NUMERIC NOT NULL, year_month VARCHAR(7) NOT NULL, UNIQUE(user_id, category, year_month));""")
        
        admin_hash = hash_password("admin123")
        c.execute("INSERT INTO users (username, password_hash, role, status) VALUES ('admin', %s, 'admin', 'active') ON CONFLICT (username) DO NOTHING;", (admin_hash,))
        
        conn.commit()
        c.close()
        conn.close()
    except Exception as e:
        st.error(f"DB Init Error: {e}")

init_cloud_db()

# --- 3. SESSION STATES ---
if "user" not in st.session_state:
    st.session_state.user = None
if "current_page" not in st.session_state:
    st.session_state.current_page = "Home"
if "currency" not in st.session_state:
    st.session_state.currency = "KWD (د.ك)"

# Navigation Helper Function
def go_to(page):
    st.session_state.current_page = page

# --- 4. LOGIN SCREEN ---
if st.session_state.user is None:
    st.markdown("<br><br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #4ade80;'>💎 Finance Cloud</h1>", unsafe_allow_html=True)
    
    with st.form("login_form"):
        username = st.text_input("Username", placeholder="admin")
        password = st.text_input("Password", type="password", placeholder="admin123")
        submit = st.form_submit_button("Secure Login", use_container_width=True)

    if submit:
        p_hash = hash_password(password)
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("SELECT id, username, role, status FROM users WHERE username=%s AND password_hash=%s;", (username.strip(), p_hash))
        row = c.fetchone()
        
        if row:
            if row[3] == 'inactive':
                st.error("❌ Account is INACTIVE.")
            else:
                st.session_state.user = {"id": row[0], "username": row[1], "role": row[2]}
                c.execute("SELECT COUNT(*) FROM accounts WHERE user_id=%s;", (row[0],))
                if c.fetchone()[0] == 0:
                    c.execute("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, 'Main Bank', 'Bank', 0.0), (%s, 'Cash Wallet', 'Cash', 0.0);", (row[0], row[0]))
                    conn.commit()
                st.rerun()
        else:
            st.error("Invalid Credentials!")
        c.close()
        conn.close()

# --- 5. MAIN APP ---
else:
    uid = st.session_state.user['id']
    curr = st.session_state.currency.split()[0]
    
    # Global Back Button (Hidden on Home page)
    if st.session_state.current_page != "Home":
        if st.button("⬅️ Back to Home Menu", use_container_width=True):
            go_to("Home")
            st.rerun()
        st.markdown("<hr style='border-color: #1e5249;'>", unsafe_allow_html=True)

    # ================= HOME MENU (Grid Layout) =================
    if st.session_state.current_page == "Home":
        st.markdown(f"<h2>Hello 👤 {st.session_state.user['username'].capitalize()}</h2>", unsafe_allow_html=True)
        
        # Currency Selector
        new_curr = st.selectbox("💱 Currency", ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"], index=["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"].index(st.session_state.currency))
        if new_curr != st.session_state.currency:
            st.session_state.currency = new_curr
            st.rerun()

        st.markdown("### 🧭 Main Menu")
        
        # Mobile-Style Grid Buttons
        col1, col2 = st.columns(2)
        with col1:
            if st.button("📊 Dashboard", use_container_width=True):
                go_to("Dashboard")
                st.rerun()
            if st.button("💸 Transactions", use_container_width=True):
                go_to("Transactions")
                st.rerun()
            if st.button("🎯 Budgets", use_container_width=True):
                go_to("Budgets")
                st.rerun()
        
        with col2:
            if st.button("🏠 Assets", use_container_width=True):
                go_to("Assets")
                st.rerun()
            if st.button("🏦 Transfer", use_container_width=True):
                go_to("Transfer")
                st.rerun()
            if st.button("🔔 Inbox", use_container_width=True):
                go_to("Inbox")
                st.rerun()

        if st.session_state.user['role'] == 'admin':
            st.markdown("<hr style='border-color: #1e5249;'>", unsafe_allow_html=True)
            if st.button("🔑 Admin Panel", use_container_width=True):
                go_to("Admin")
                st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.user = None
            go_to("Home")
            st.rerun()

    # ================= DASHBOARD =================
    elif st.session_state.current_page == "Dashboard":
        st.title("📊 Analytics")
        conn = get_db_connection()
        c = conn.cursor()
        
        c.execute("SELECT SUM(balance) FROM accounts WHERE user_id=%s;", (uid,))
        bank_bal = float(c.fetchone()[0] or 0.0)
        c.execute("SELECT SUM(estimated_value) FROM custom_assets WHERE user_id=%s;", (uid,))
        asset_val = float(c.fetchone()[0] or 0.0)
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=%s AND tx_type='Expense';", (uid,))
        tot_exp = float(c.fetchone()[0] or 0.0)
        net_worth = bank_bal + asset_val

        # HTML KPI Cards
        st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0f3d36, #0a2521); padding: 20px; border-radius: 15px; border: 1px solid #1e5249; margin-bottom: 15px;">
            <p style="margin:0; color:#88aba6;">💎 Total Net Worth</p>
            <h2 style="margin:0; color:#4ade80;">{curr} {net_worth:,.2f}</h2>
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 15px;">
            <div style="background-color: #12332e; padding: 15px; border-radius: 15px; border: 1px solid #1e5249;">
                <p style="margin:0; color:#88aba6;">🏦 Bank Balances</p>
                <h4 style="margin:0; color:#e0f2f1;">{curr} {bank_bal:,.2f}</h4>
            </div>
            <div style="background-color: #12332e; padding: 15px; border-radius: 15px; border: 1px solid #1e5249;">
                <p style="margin:0; color:#88aba6;">🏠 Property & Assets</p>
                <h4 style="margin:0; color:#e0f2f1;">{curr} {asset_val:,.2f}</h4>
            </div>
        </div>
        <div style="background-color: #12332e; padding: 15px; border-radius: 15px; border: 1px solid #1e5249;">
            <p style="margin:0; color:#f87171;">📉 Lifetime Expenses</p>
            <h4 style="margin:0; color:#e0f2f1;">{curr} {tot_exp:,.2f}</h4>
        </div>
        """, unsafe_allow_html=True)

        tx_df = pd.read_sql_query("SELECT tx_date, tx_type, category, amount FROM transactions WHERE user_id=%s", conn, params=(uid,))
        conn.close()

        if not tx_df.empty:
            st.markdown("<br><h4>Financial Dynamics</h4>", unsafe_allow_html=True)
            exp_df = tx_df[tx_df['tx_type'] == 'Expense']
            if not exp_df.empty:
                fig_pie = px.pie(exp_df, values='amount', names='category', hole=0.5)
                fig_pie.update_layout(paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)', font=dict(color='#e0f2f1'))
                st.plotly_chart(fig_pie, use_container_width=True)
        else:
            st.info("Record transactions to see charts.")

    # ================= ASSETS =================
    elif st.session_state.current_page == "Assets":
        st.title("🏠 Custom Assets")
        with st.form("asset_form"):
            a_name = st.text_input("Asset Name (e.g., Land)")
            a_cat = st.selectbox("Category", ["Real Estate", "Gold", "Vehicles", "Stocks", "Crypto"])
            a_val = st.number_input("Estimated Value", min_value=0.0, step=100.0)
            btn = st.form_submit_button("Save Asset", use_container_width=True)
            
        if btn and a_name:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("INSERT INTO custom_assets (user_id, asset_name, category, estimated_value) VALUES (%s, %s, %s, %s);", (uid, a_name, a_cat, a_val))
            conn.commit()
            c.close()
            conn.close()
            st.success("Asset Saved!")
            st.rerun()

        conn = get_db_connection()
        df_assets = pd.read_sql_query("SELECT asset_name as \"Asset\", estimated_value as \"Value\" FROM custom_assets WHERE user_id=%s", conn, params=(uid,))
        conn.close()
        if not df_assets.empty:
            df_assets["Value"] = df_assets["Value"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(df_assets, use_container_width=True, hide_index=True)

    # ================= TRANSACTIONS =================
    elif st.session_state.current_page == "Transactions":
        st.title("💸 Transactions")
        conn = get_db_connection()
        acc_df = pd.read_sql_query("SELECT id, name FROM accounts WHERE user_id=%s", conn, params=(uid,))
        acc_dict = dict(zip(acc_df['name'], acc_df['id'])) if not acc_df.empty else {}
        
        with st.form("tx_form"):
            tx_type = st.selectbox("Type", ["Expense", "Income"])
            acc_name = st.selectbox("Account", list(acc_dict.keys()) if acc_dict else ["None"])
            cat = st.selectbox("Category", ["Food & Dining", "Rent & Utilities", "Salary", "Shopping", "Transport"])
            tx_amt = st.number_input("Amount", min_value=0.01, step=10.0)
            tx_date = st.date_input("Date")
            tx_desc = st.text_input("Notes")
            btn = st.form_submit_button("Save Transaction", use_container_width=True)
            
        if btn and acc_dict:
            c = conn.cursor()
            acc_id = acc_dict[acc_name]
            c.execute("INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) VALUES (%s, %s, %s, %s, %s, %s, %s);", (uid, acc_id, tx_date, tx_type, cat, tx_amt, tx_desc))
            bal_change = tx_amt if tx_type == "Income" else -tx_amt
            c.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (bal_change, acc_id))
            conn.commit()
            c.close()
            st.success("Transaction Saved!")
            st.rerun()

        tx_history = pd.read_sql_query("SELECT tx_date as \"Date\", tx_type as \"Type\", amount as \"Amount\" FROM transactions WHERE user_id=%s ORDER BY tx_date DESC LIMIT 20", conn, params=(uid,))
        conn.close()
        if not tx_history.empty:
            tx_history["Amount"] = tx_history["Amount"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(tx_history, use_container_width=True, hide_index=True)

    # ================= TRANSFER =================
    elif st.session_state.current_page == "Transfer":
        st.title("🏦 Money Transfer")
        conn = get_db_connection()
        accs = pd.read_sql_query("SELECT name FROM accounts WHERE user_id=%s", conn, params=(uid,))
        conn.close()

        if len(accs) >= 2:
            with st.form("transfer_form"):
                f_acc = st.selectbox("From Account", accs['name'])
                t_acc = st.selectbox("To Account", accs['name'], index=1)
                amt = st.number_input("Amount", min_value=0.01, step=10.0)
                btn = st.form_submit_button("Execute Transfer", use_container_width=True)
                
            if btn:
                if f_acc == t_acc:
                    st.error("Accounts must be different!")
                else:
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("UPDATE accounts SET balance = balance - %s WHERE name=%s AND user_id=%s;", (amt, f_acc, uid))
                    c.execute("UPDATE accounts SET balance = balance + %s WHERE name=%s AND user_id=%s;", (amt, t_acc, uid))
                    conn.commit()
                    c.close()
                    conn.close()
                    st.success("Transfer Complete!")
                    st.rerun()
        else:
            st.warning("You need 2 accounts for this.")

    # ================= BUDGETS =================
    elif st.session_state.current_page == "Budgets":
        st.title("🎯 Budgets")
        curr_month = datetime.now().strftime("%Y-%m")
        with st.form("budget_form"):
            b_cat = st.selectbox("Category", ["Food & Dining", "Rent & Utilities", "Shopping", "Transport"])
            b_limit = st.number_input("Monthly Limit", min_value=1.0, step=50.0)
            btn = st.form_submit_button("Set Budget", use_container_width=True)
            
        if btn:
            conn = get_db_connection()
            c = conn.cursor()
            c.execute("INSERT INTO budgets (user_id, category, monthly_limit, year_month) VALUES (%s, %s, %s, %s) ON CONFLICT(user_id, category, year_month) DO UPDATE SET monthly_limit=EXCLUDED.monthly_limit;", (uid, b_cat, b_limit, curr_month))
            conn.commit()
            c.close()
            conn.close()
            st.success("Budget Set!")
            st.rerun()

        st.subheader("Current Budgets")
        conn = get_db_connection()
        budgets = pd.read_sql_query("SELECT category, monthly_limit FROM budgets WHERE user_id=%s AND year_month=%s", conn, params=(uid, curr_month))
        tx_spent = pd.read_sql_query("SELECT category, SUM(amount) as spent FROM transactions WHERE user_id=%s AND tx_type='Expense' AND TO_CHAR(tx_date, 'YYYY-MM')=%s GROUP BY category", conn, params=(uid, curr_month))
        conn.close()
        
        if not budgets.empty:
            for _, r in budgets.iterrows():
                cat, limit = r['category'], float(r['monthly_limit'])
                spent_row = tx_spent[tx_spent['category'] == cat]
                spent = float(spent_row['spent'].values[0]) if not spent_row.empty else 0.0
                progress = min(spent / limit, 1.0)
                st.write(f"**{cat}** ({curr} {spent:,.2f} / {curr} {limit:,.2f})")
                st.progress(progress)

    # ================= INBOX =================
    elif st.session_state.current_page == "Inbox":
        st.title("🔔 Inbox")
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND is_read=FALSE;", (uid,))
        conn.commit()
        notifs = pd.read_sql_query("SELECT title as \"Title\", message as \"Message\", created_at as \"Date\" FROM notifications WHERE user_id=%s ORDER BY created_at DESC", conn, params=(uid,))
        conn.close()
        if not notifs.empty:
            notifs["Date"] = pd.to_datetime(notifs["Date"]).dt.strftime('%Y-%m-%d')
            st.dataframe(notifs, use_container_width=True, hide_index=True)
        else:
            st.info("Inbox empty.")

    # ================= ADMIN =================
    elif st.session_state.current_page == "Admin":
        st.title("🔑 Admin Panel")
        conn = get_db_connection()
        users_df = pd.read_sql_query("SELECT username as \"User\", status as \"Status\" FROM users", conn)
        
        with st.form("status_form"):
            sel_u = st.selectbox("Select User", users_df[users_df['User'] != 'admin']['User'].tolist())
            btn = st.form_submit_button("Toggle Active/Inactive", use_container_width=True)
        if btn and sel_u:
            c = conn.cursor()
            c.execute("SELECT status FROM users WHERE username=%s;", (sel_u,))
            nxt_s = 'inactive' if c.fetchone()[0] == 'active' else 'active'
            c.execute("UPDATE users SET status=%s WHERE username=%s;", (nxt_s, sel_u))
            conn.commit()
            st.success(f"{sel_u} status changed to {nxt_s}")
            st.rerun()

        st.markdown("---")
        with st.form("bcast_form"):
            b_title = st.text_input("Broadcast Title")
            b_msg = st.text_area("Message")
            btn2 = st.form_submit_button("Send to All Users", use_container_width=True)
        if btn2 and b_title:
            c = conn.cursor()
            c.execute("SELECT id FROM users;")
            for u in c.fetchall():
                c.execute("INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s);", (u[0], b_title, b_msg))
            conn.commit()
            st.success("Broadcast sent!")
            st.rerun()
        conn.close()
