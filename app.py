import streamlit as st
import psycopg2
import psycopg2.extras
import pandas as pd
import plotly.express as px
import hashlib
from datetime import datetime, date
import os

# ==========================================
# 1. PAGE CONFIGURATION & SETUP
# ==========================================
st.set_page_config(
    page_title="FinMaster Pro | Wealth Management",
    page_icon="💎",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Currency Configuration
CURRENCY_RATES = {
    "USD $": {"rate": 1.0, "symbol": "$"},
    "KWD د.ك": {"rate": 0.31, "symbol": "د.ك"},
    "EUR €": {"rate": 0.92, "symbol": "€"},
    "LKR Rs": {"rate": 320.0, "symbol": "Rs"}
}

# ==========================================
# 2. DATABASE UTILITIES & SECURITY
# ==========================================
def get_connection():
    """Establish a fresh database connection using secrets."""
    try:
        return psycopg2.connect(
            st.secrets["CLOUD_DB_URL"],
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        st.error(f"🚨 Database Connection Error: {e}")
        st.stop()

def fetch_data(query, params=None):
    """Fetch data securely using parameterized queries."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(query, params)
        data = cur.fetchall()
    conn.close()
    return data

def execute_query(query, params=None):
    """Execute insert/update/delete securely."""
    conn = get_connection()
    with conn.cursor() as cur:
        cur.execute(query, params)
    conn.commit()
    conn.close()

def hash_password(password: str) -> str:
    """Secure PBKDF2 hashing using a stored secret salt."""
    salt = st.secrets.get("SECRET_SALT", "default_salt").encode('utf-8')
    pwdhash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return pwdhash.hex()

def format_currency(amount):
    """Format numeric values dynamically based on selected currency."""
    if amount is None:
        amount = 0.0
    curr = st.session_state.get('currency', 'USD $')
    rate = CURRENCY_RATES[curr]['rate']
    symbol = CURRENCY_RATES[curr]['symbol']
    converted = float(amount) * rate
    return f"{symbol} {converted:,.2f}"

# ==========================================
# 3. SCHEMA INITIALIZATION (Auto-Migration)
# ==========================================
@st.cache_resource
def init_cloud_db():
    conn = get_connection()
    with conn.cursor() as cur:
        # Users Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) DEFAULT 'user',
                status VARCHAR(20) DEFAULT 'active'
            )
        """)
        # Accounts Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS accounts (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                name VARCHAR(100),
                type VARCHAR(50),
                balance NUMERIC(15, 2) DEFAULT 0.00
            )
        """)
        # Custom Assets Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS custom_assets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                asset_name VARCHAR(100),
                category VARCHAR(50),
                estimated_value NUMERIC(15, 2) DEFAULT 0.00
            )
        """)
        # Transactions Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                account_id INTEGER REFERENCES accounts(id),
                tx_date DATE,
                tx_type VARCHAR(20),
                category VARCHAR(50),
                amount NUMERIC(15, 2),
                description TEXT
            )
        """)
        # Notifications Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                title VARCHAR(100),
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_read BOOLEAN DEFAULT FALSE
            )
        """)
        # Budgets Table
        cur.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
                id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(id),
                category VARCHAR(50),
                monthly_limit NUMERIC(15, 2)
            )
        """)
        
        # Insert Default Admin User
        admin_hash = hash_password('admin123')
        cur.execute("""
            INSERT INTO users (username, password_hash, role, status)
            VALUES ('admin', %s, 'admin', 'active')
            ON CONFLICT (username) DO NOTHING;
        """, (admin_hash,))
    conn.commit()
    conn.close()

# ==========================================
# 4. AUTHENTICATION MODULE
# ==========================================
def auth_system():
    st.markdown("<h1 style='text-align: center; color: #2E86C1;'>💎 FinMaster Pro</h1>", unsafe_allow_html=True)
    st.markdown("<h4 style='text-align: center; color: gray;'>Enterprise Financial & Net Worth Management</h4>", unsafe_allow_html=True)
    st.divider()
    
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            with st.form("login_form"):
                log_user = st.text_input("Username")
                log_pass = st.text_input("Password", type="password")
                sub_login = st.form_submit_button("Access Dashboard", use_container_width=True)
                
                if sub_login:
                    user_data = fetch_data("SELECT * FROM users WHERE username = %s", (log_user,))
                    if user_data:
                        user = user_data[0]
                        if user['password_hash'] == hash_password(log_pass):
                            if user['status'] == 'inactive':
                                st.error("🚫 Account is suspended. Contact administrator.")
                            else:
                                st.session_state['user_id'] = user['id']
                                st.session_state['username'] = user['username']
                                st.session_state['role'] = user['role']
                                st.rerun()
                        else:
                            st.error("❌ Invalid credentials!")
                    else:
                        st.error("❌ User not found!")
                        
        with tab2:
            with st.form("register_form"):
                reg_user = st.text_input("Choose Username")
                reg_pass = st.text_input("Choose Password", type="password")
                sub_reg = st.form_submit_button("Create Account", use_container_width=True)
                
                if sub_reg:
                    if len(reg_user) < 3 or len(reg_pass) < 5:
                        st.warning("⚠️ Username > 2 chars, Password > 4 chars required.")
                    else:
                        exists = fetch_data("SELECT id FROM users WHERE username = %s", (reg_user,))
                        if exists:
                            st.error("⚠️ Username already taken!")
                        else:
                            execute_query(
                                "INSERT INTO users (username, password_hash) VALUES (%s, %s)",
                                (reg_user, hash_password(reg_pass))
                            )
                            st.success("✅ Account created successfully! Please log in.")

# ==========================================
# 5. CORE APP MODULES
# ==========================================
def sidebar_nav():
    with st.sidebar:
        st.markdown(f"### 👋 Welcome, {st.session_state['username'].title()}")
        st.selectbox("🌍 Select Currency", options=list(CURRENCY_RATES.keys()), key='currency')
        
        st.divider()
        st.markdown("### 📬 Quick Alerts")
        unread = fetch_data("SELECT COUNT(*) as c FROM notifications WHERE user_id = %s AND is_read = FALSE", (st.session_state['user_id'],))[0]['c']
        if unread > 0:
            st.warning(f"You have {unread} unread message(s)!")
        else:
            st.success("All caught up!")
            
        st.divider()
        if st.button("🚪 Logout", use_container_width=True):
            st.session_state.clear()
            st.rerun()

def tab_dashboard():
    st.header("📊 Financial Dashboard")
    uid = st.session_state['user_id']
    
    # KPIs Data Fetching
    acc_data = fetch_data("SELECT SUM(balance) as total FROM accounts WHERE user_id = %s", (uid,))
    asset_data = fetch_data("SELECT SUM(estimated_value) as total FROM custom_assets WHERE user_id = %s", (uid,))
    exp_data = fetch_data("SELECT SUM(amount) as total FROM transactions WHERE user_id = %s AND tx_type = 'Expense' AND EXTRACT(MONTH FROM tx_date) = %s", (uid, date.today().month))
    
    tot_cash = acc_data[0]['total'] or 0.0
    tot_assets = asset_data[0]['total'] or 0.0
    tot_exp = exp_data[0]['total'] or 0.0
    net_worth = float(tot_cash) + float(tot_assets)
    
    # Render KPI Cards
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("💎 Total Net Worth", format_currency(net_worth))
    col2.metric("🏦 Bank Balances", format_currency(tot_cash))
    col3.metric("🏡 Portfolio Assets", format_currency(tot_assets))
    col4.metric("📉 Expenses (This Month)", format_currency(tot_exp))
    
    st.divider()
    
    # Charts
    colA, colB = st.columns(2)
    
    with colA:
        st.subheader("🍩 Expense Breakdown")
        df_exp = pd.DataFrame(fetch_data("SELECT category, SUM(amount) as total FROM transactions WHERE user_id = %s AND tx_type = 'Expense' GROUP BY category", (uid,)))
        if not df_exp.empty:
            fig1 = px.pie(df_exp, values='total', names='category', hole=0.4, color_discrete_sequence=px.colors.qualitative.Pastel)
            st.plotly_chart(fig1, use_container_width=True)
        else:
            st.info("No expense data available.")
            
    with colB:
        st.subheader("📈 Income vs Expense (Monthly)")
        df_trend = pd.DataFrame(fetch_data("""
            SELECT TO_CHAR(tx_date, 'YYYY-MM') as month, tx_type, SUM(amount) as total 
            FROM transactions WHERE user_id = %s 
            GROUP BY month, tx_type ORDER BY month
        """, (uid,)))
        if not df_trend.empty:
            fig2 = px.bar(df_trend, x='month', y='total', color='tx_type', barmode='group', color_discrete_map={'Income': '#2ECC71', 'Expense': '#E74C3C'})
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No transaction data available.")

def tab_transactions():
    st.header("💸 Transaction Manager")
    uid = st.session_state['user_id']
    
    accounts = fetch_data("SELECT id, name, balance FROM accounts WHERE user_id = %s", (uid,))
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("➕ Add Transaction")
        if not accounts:
            st.warning("⚠️ Please create an account first!")
            with st.form("init_account"):
                acc_name = st.text_input("Account Name (e.g., Checking)")
                acc_type = st.selectbox("Type", ["Bank", "Cash", "Credit Card"])
                if st.form_submit_button("Create Account"):
                    execute_query("INSERT INTO accounts (user_id, name, type) VALUES (%s, %s, %s)", (uid, acc_name, acc_type))
                    st.rerun()
        else:
            with st.form("tx_form"):
                acc_map = {f"{a['name']} ({format_currency(a['balance'])})": a['id'] for a in accounts}
                sel_acc = st.selectbox("Account", options=list(acc_map.keys()))
                tx_type = st.radio("Type", ["Income", "Expense"], horizontal=True)
                tx_cat = st.selectbox("Category", ["Salary", "Food", "Rent", "Utilities", "Entertainment", "Other"])
                tx_amt = st.number_input("Amount (Base Currency)", min_value=0.01, step=10.0, format="%.2f")
                tx_date = st.date_input("Date")
                tx_desc = st.text_input("Description")
                
                if st.form_submit_button("Save Transaction"):
                    acc_id = acc_map[sel_acc]
                    conn = get_connection()
                    try:
                        with conn.cursor() as cur:
                            cur.execute("""
                                INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) 
                                VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """, (uid, acc_id, tx_date, tx_type, tx_cat, tx_amt, tx_desc))
                            
                            if tx_type == 'Expense':
                                cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (tx_amt, acc_id))
                            else:
                                cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (tx_amt, acc_id))
                            conn.commit()
                        st.success("✅ Transaction Saved!")
                        st.rerun()
                    except Exception as e:
                        conn.rollback()
                        st.error(f"Error: {e}")
                    finally:
                        conn.close()
    with col2:
        st.subheader("📋 Recent Transactions")
        df_tx = pd.DataFrame(fetch_data("""
            SELECT t.tx_date as "Date", a.name as "Account", t.tx_type as "Type", 
                   t.category as "Category", t.amount as "Amount", t.description as "Description"
            FROM transactions t JOIN accounts a ON t.account_id = a.id
            WHERE t.user_id = %s ORDER BY t.tx_date DESC LIMIT 50
        """, (uid,)))
        if not df_tx.empty:
            df_tx['Amount'] = df_tx['Amount'].apply(lambda x: format_currency(x))
            st.dataframe(df_tx, use_container_width=True, hide_index=True)
        else:
            st.info("No transactions found.")

def tab_transfers():
    st.header("🔄 Internal Money Transfer")
    uid = st.session_state['user_id']
    accounts = fetch_data("SELECT id, name, balance FROM accounts WHERE user_id = %s", (uid,))
    
    if len(accounts) < 2:
        st.warning("⚠️ You need at least two accounts to make a transfer.")
        return
        
    with st.form("transfer_form"):
        acc_map = {f"{a['name']}": a['id'] for a in accounts}
        col1, col2 = st.columns(2)
        with col1:
            from_acc = st.selectbox("Source Account", options=list(acc_map.keys()))
        with col2:
            to_acc = st.selectbox("Destination Account", options=list(acc_map.keys()), index=1)
            
        amount = st.number_input("Amount to Transfer", min_value=0.01, step=10.0, format="%.2f")
        
        if st.form_submit_button("Execute Transfer"):
            if from_acc == to_acc:
                st.error("❌ Source and Destination accounts must be different!")
            else:
                fid, tid = acc_map[from_acc], acc_map[to_acc]
                conn = get_connection()
                try:
                    with conn.cursor() as cur:
                        cur.execute("UPDATE accounts SET balance = balance - %s WHERE id = %s", (amount, fid))
                        cur.execute("UPDATE accounts SET balance = balance + %s WHERE id = %s", (amount, tid))
                        cur.execute("INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) VALUES (%s, %s, CURRENT_DATE, 'Expense', 'Transfer Out', %s, 'Internal Transfer'), (%s, %s, CURRENT_DATE, 'Income', 'Transfer In', %s, 'Internal Transfer')", (uid, fid, amount, uid, tid, amount))
                        conn.commit()
                    st.success("✅ Transfer Complete!")
                    st.rerun()
                except Exception as e:
                    conn.rollback()
                    st.error("Error executing transfer.")
                finally:
                    conn.close()

def tab_assets():
    st.header("🏡 Property & Custom Assets")
    uid = st.session_state['user_id']
    
    col1, col2 = st.columns([1, 2])
    with col1:
        with st.form("asset_form"):
            a_name = st.text_input("Asset Name (e.g., Downtown Apartment)")
            a_cat = st.selectbox("Category", ["Real Estate", "Vehicle", "Crypto", "Gold/Metals", "Other"])
            a_val = st.number_input("Estimated Value", min_value=0.00, step=1000.0, format="%.2f")
            if st.form_submit_button("Add Asset"):
                execute_query("INSERT INTO custom_assets (user_id, asset_name, category, estimated_value) VALUES (%s, %s, %s, %s)", (uid, a_name, a_cat, a_val))
                st.success("✅ Asset added!")
                st.rerun()
                
    with col2:
        df_assets = pd.DataFrame(fetch_data("SELECT asset_name as \"Asset\", category as \"Category\", estimated_value as \"Value\" FROM custom_assets WHERE user_id = %s", (uid,)))
        if not df_assets.empty:
            df_assets['Value'] = df_assets['Value'].apply(lambda x: format_currency(x))
            st.dataframe(df_assets, use_container_width=True, hide_index=True)
        else:
            st.info("No assets listed.")

def tab_budgets():
    st.header("🎯 Smart Budgets")
    uid = st.session_state['user_id']
    
    with st.expander("➕ Set New Budget Limit"):
        with st.form("budget_form"):
            b_cat = st.selectbox("Category", ["Food", "Rent", "Utilities", "Entertainment", "Other"])
            b_limit = st.number_input("Monthly Limit", min_value=1.0, step=50.0, format="%.2f")
            if st.form_submit_button("Save Budget"):
                # Upsert logic
                exists = fetch_data("SELECT id FROM budgets WHERE user_id = %s AND category = %s", (uid, b_cat))
                if exists:
                    execute_query("UPDATE budgets SET monthly_limit = %s WHERE id = %s", (b_limit, exists[0]['id']))
                else:
                    execute_query("INSERT INTO budgets (user_id, category, monthly_limit) VALUES (%s, %s, %s)", (uid, b_cat, b_limit))
                st.rerun()

    budgets = fetch_data("SELECT category, monthly_limit FROM budgets WHERE user_id = %s", (uid,))
    if budgets:
        for b in budgets:
            cat = b['category']
            limit = b['monthly_limit']
            spent_data = fetch_data("SELECT SUM(amount) as s FROM transactions WHERE user_id = %s AND tx_type = 'Expense' AND category = %s AND EXTRACT(MONTH FROM tx_date) = %s", (uid, cat, date.today().month))
            spent = spent_data[0]['s'] or 0.0
            
            st.markdown(f"**{cat}** (Spent: {format_currency(spent)} / Limit: {format_currency(limit)})")
            prog = min(float(spent) / float(limit), 1.0) if float(limit) > 0 else 1.0
            st.progress(prog)
    else:
        st.info("No budgets set.")

def tab_notifications():
    st.header("🔔 Inbox")
    uid = st.session_state['user_id']
    notifs = fetch_data("SELECT * FROM notifications WHERE user_id = %s ORDER BY created_at DESC", (uid,))
    
    if notifs:
        for n in notifs:
            color = "green" if n['is_read'] else "red"
            status = "Read" if n['is_read'] else "NEW"
            with st.container():
                st.markdown(f"<p style='color:{color}'><b>[{status}] {n['title']}</b> - {n['created_at'].strftime('%Y-%m-%d %H:%M')}</p>", unsafe_allow_html=True)
                st.write(n['message'])
                if not n['is_read']:
                    if st.button("Mark as Read", key=f"read_{n['id']}"):
                        execute_query("UPDATE notifications SET is_read = TRUE WHERE id = %s", (n['id'],))
                        st.rerun()
                st.divider()
    else:
        st.info("Inbox is empty.")

def tab_admin():
    st.header("⚙️ Master Admin Panel")
    
    st.subheader("👥 User Management")
    users = fetch_data("SELECT id, username, role, status FROM users")
    df_users = pd.DataFrame(users)
    st.dataframe(df_users, use_container_width=True, hide_index=True)
    
    col1, col2 = st.columns(2)
    with col1:
        with st.form("status_update"):
            st.markdown("**Toggle User Access**")
            target_user = st.selectbox("Select User", [u['username'] for u in users if u['username'] != 'admin'])
            new_status = st.radio("Status", ["active", "inactive"], horizontal=True)
            if st.form_submit_button("Update Status"):
                execute_query("UPDATE users SET status = %s WHERE username = %s", (new_status, target_user))
                st.success(f"User {target_user} updated to {new_status}.")
                st.rerun()
                
    with col2:
        with st.form("broadcast_form"):
            st.markdown("**📢 Send Broadcast Message**")
            b_title = st.text_input("Title")
            b_msg = st.text_area("Message")
            if st.form_submit_button("Send to All Users"):
                user_ids = [u['id'] for u in users]
                conn = get_connection()
                with conn.cursor() as cur:
                    for uid in user_ids:
                        cur.execute("INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s)", (uid, b_title, b_msg))
                conn.commit()
                conn.close()
                st.success("✅ Broadcast sent successfully!")

# ==========================================
# 6. MAIN APPLICATION ROUTING
# ==========================================
def main():
    init_cloud_db()
    
    if 'user_id' not in st.session_state:
        auth_system()
    else:
        sidebar_nav()
        
        # Admin gets an extra tab
        if st.session_state.get('role') == 'admin':
            t1, t2, t3, t4, t5, t6, t7 = st.tabs(["📊 Dashboard", "💸 Transactions", "🔄 Transfers", "🏡 Assets", "🎯 Budgets", "🔔 Notifications", "⚙️ Admin"])
            tabs_dict = {t1: tab_dashboard, t2: tab_transactions, t3: tab_transfers, t4: tab_assets, t5: tab_budgets, t6: tab_notifications, t7: tab_admin}
        else:
            t1, t2, t3, t4, t5, t6 = st.tabs(["📊 Dashboard", "💸 Transactions", "🔄 Transfers", "🏡 Assets", "🎯 Budgets", "🔔 Notifications"])
            tabs_dict = {t1: tab_dashboard, t2: tab_transactions, t3: tab_transfers, t4: tab_assets, t5: tab_budgets, t6: tab_notifications}
            
        for tab, func in tabs_dict.items():
            with tab:
                func()

if __name__ == "__main__":
    main()