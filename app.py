import streamlit as st
import psycopg2
import hashlib
from datetime import date, datetime
import pandas as pd
import plotly.express as px

# --- 1. CONFIGURATION & SETUP ---
st.set_page_config(page_title="Smart Finance Enterprise", page_icon="💎", layout="wide")

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

if "user" not in st.session_state:
    st.session_state.user = None

# --- 3. AUTHENTICATION (LOGIN) ---
if st.session_state.user is None:
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>💎 Smart Finance Cloud</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center; color: gray;'>Enterprise Asset & Cashflow Manager</p>", unsafe_allow_html=True)
        
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
    
    # Sidebar Setup
    st.sidebar.markdown(f"### 👤 {st.session_state.user['username'].upper()}")
    if st.sidebar.button("🚪 Logout", use_container_width=True):
        st.session_state.user = None
        st.rerun()
    st.sidebar.markdown("---")
    
    currency_choice = st.sidebar.selectbox("💱 Currency", ["KWD (د.ك)", "USD ($)", "EUR (€)", "LKR (Rs)"])
    curr = currency_choice.split()[0]

    menu_options = ["📊 Executive Dashboard", "🏠 Asset Portfolio", "💸 Transactions", "🏦 Money Transfer", "🎯 Budgets & Goals", "🔔 Inbox"]
    if st.session_state.user['role'] == 'admin':
        menu_options.append("🔑 Admin Control Panel")
        
    choice = st.sidebar.radio("Navigation Menu", menu_options)

    # --- MODULE 1: EXECUTIVE DASHBOARD ---
    if choice == "📊 Executive Dashboard":
        st.title("📊 Net Worth & Financial Analytics")
        
        conn = get_db_connection()
        
        # Get KPI Data
        c = conn.cursor()
        c.execute("SELECT SUM(balance) FROM accounts WHERE user_id=%s;", (uid,))
        bank_bal = float(c.fetchone()[0] or 0.0)

        c.execute("SELECT SUM(estimated_value) FROM custom_assets WHERE user_id=%s;", (uid,))
        asset_val = float(c.fetchone()[0] or 0.0)
        
        c.execute("SELECT SUM(amount) FROM transactions WHERE user_id=%s AND tx_type='Expense';", (uid,))
        tot_exp = float(c.fetchone()[0] or 0.0)

        net_worth = bank_bal + asset_val

        # KPI Metric Cards
        kpi1, kpi2, kpi3, kpi4 = st.columns(4)
        kpi1.metric("💎 Total Net Worth", f"{curr} {net_worth:,.2f}")
        kpi2.metric("🏦 Bank Balances", f"{curr} {bank_bal:,.2f}")
        kpi3.metric("🏠 Property & Assets", f"{curr} {asset_val:,.2f}")
        kpi4.metric("📉 Lifetime Expenses", f"{curr} {tot_exp:,.2f}")
        st.markdown("---")

        # Interactive Data Visualizations using Plotly
        tx_df = pd.read_sql_query("SELECT tx_date, tx_type, category, amount FROM transactions WHERE user_id=%s", conn, params=(uid,))
        conn.close()

        if not tx_df.empty:
            col_chart1, col_chart2 = st.columns(2)
            
            with col_chart1:
                st.subheader("Expense Breakdown")
                exp_df = tx_df[tx_df['tx_type'] == 'Expense']
                if not exp_df.empty:
                    fig_pie = px.pie(exp_df, values='amount', names='category', hole=0.4, color_discrete_sequence=px.colors.sequential.RdBu)
                    st.plotly_chart(fig_pie, use_container_width=True)
                else:
                    st.info("No expense data for chart.")

            with col_chart2:
                st.subheader("Income vs Expense (Timeline)")
                tx_df['Month'] = pd.to_datetime(tx_df['tx_date']).dt.strftime('%Y-%m')
                trend_df = tx_df.groupby(['Month', 'tx_type'])['amount'].sum().reset_index()
                if not trend_df.empty:
                    fig_bar = px.bar(trend_df, x='Month', y='amount', color='tx_type', barmode='group', color_discrete_map={'Income':'#2ca02c', 'Expense':'#d62728'})
                    st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("💡 Record transactions to unlock AI-powered financial charts!")

    # --- MODULE 2: ASSET PORTFOLIO ---
    elif choice == "🏠 Asset Portfolio":
        st.title("🏠 Custom Assets & Net Worth Builders")
        
        with st.expander("➕ Register New Asset", expanded=True):
            with st.form("asset_form"):
                c1, c2, c3 = st.columns(3)
                a_name = c1.text_input("Asset Name (e.g., Tesla Model 3)")
                a_cat = c2.selectbox("Asset Class", ["Real Estate", "Gold", "Vehicles", "Stocks", "Crypto", "Business"])
                a_val = c3.number_input("Estimated Market Value", min_value=0.0, step=100.0, format="%.2f")
                if st.form_submit_button("Save Asset to Portfolio") and a_name:
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
    elif choice == "💸 Transactions":
        st.title("💸 Smart Transaction Manager")
        
        conn = get_db_connection()
        acc_df = pd.read_sql_query("SELECT id, name FROM accounts WHERE user_id=%s", conn, params=(uid,))
        acc_dict = dict(zip(acc_df['name'], acc_df['id'])) if not acc_df.empty else {}
        
        with st.form("tx_form"):
            c1, c2, c3 = st.columns(3)
            tx_type = c1.selectbox("Transaction Flow", ["Expense", "Income"])
            acc_name = c2.selectbox("Account", list(acc_dict.keys()) if acc_dict else ["No Accounts Found"])
            cat = c3.selectbox("Category", ["Food & Dining", "Rent & Utilities", "Salary", "Shopping", "Transport", "Healthcare", "Investments", "Other"])
            
            c4, c5, c6 = st.columns(3)
            tx_amt = c4.number_input("Amount", min_value=0.01, step=10.0, format="%.2f")
            tx_date = c5.date_input("Date")
            tx_desc = c6.text_input("Notes / Description")
            
            if st.form_submit_button("Commit Transaction") and acc_dict:
                c = conn.cursor()
                acc_id = acc_dict[acc_name]
                c.execute("INSERT INTO transactions (user_id, account_id, tx_date, tx_type, category, amount, description) VALUES (%s, %s, %s, %s, %s, %s, %s);",
                          (uid, acc_id, tx_date, tx_type, cat, tx_amt, tx_desc))
                
                bal_change = tx_amt if tx_type == "Income" else -tx_amt
                c.execute("UPDATE accounts SET balance = balance + %s WHERE id=%s;", (bal_change, acc_id))
                conn.commit()
                c.close()
                st.success("Transaction Synced & Balances Updated!")
                st.rerun()

        st.subheader("Transaction History")
        tx_history = pd.read_sql_query("""
            SELECT t.tx_date as "Date", a.name as "Account", t.tx_type as "Type", t.category as "Category", t.amount as "Amount", t.description as "Notes" 
            FROM transactions t JOIN accounts a ON t.account_id = a.id WHERE t.user_id=%s ORDER BY t.tx_date DESC LIMIT 50
        """, conn, params=(uid,))
        conn.close()

        if not tx_history.empty:
            tx_history["Amount"] = tx_history["Amount"].apply(lambda x: f"{curr} {float(x):,.2f}")
            st.dataframe(tx_history, use_container_width=True, hide_index=True)

    # --- MODULE 4: INTERNAL TRANSFER ---
    elif choice == "🏦 Money Transfer":
        st.title("🏦 Internal Account Routing")
        
        conn = get_db_connection()
        accs = pd.read_sql_query("SELECT name, balance FROM accounts WHERE user_id=%s", conn, params=(uid,))
        conn.close()

        if len(accs) >= 2:
            st.info("Seamlessly route funds between your accounts without affecting net income/expenses.")
            with st.form("transfer_form"):
                c1, c2 = st.columns(2)
                f_acc = c1.selectbox("Origin Account", accs['name'])
                t_acc = c2.selectbox("Destination Account", accs['name'], index=1)
                amt = st.number_input("Transfer Value", min_value=0.01, step=100.0, format="%.2f")
                
                if st.form_submit_button("Initiate Transfer"):
                    if f_acc == t_acc:
                        st.error("Origin and Destination must be distinct!")
                    else:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("UPDATE accounts SET balance = balance - %s WHERE name=%s AND user_id=%s;", (amt, f_acc, uid))
                        c.execute("UPDATE accounts SET balance = balance + %s WHERE name=%s AND user_id=%s;", (amt, t_acc, uid))
                        conn.commit()
                        c.close()
                        conn.close()
                        st.success(f"Successfully routed {curr} {amt:,.2f} from {f_acc} to {t_acc}.")
        else:
            st.warning("You need at least 2 bank accounts to utilize internal transfers.")

    # --- MODULE 5: BUDGETS & GOALS ---
    elif choice == "🎯 Budgets & Goals":
        st.title("🎯 Smart Budget Tracker")
        curr_month = datetime.now().strftime("%Y-%m")
        
        with st.form("budget_form"):
            c1, c2 = st.columns(2)
            b_cat = c1.selectbox("Category to Monitor", ["Food & Dining", "Rent & Utilities", "Shopping", "Transport"])
            b_limit = c2.number_input("Monthly Limit", min_value=1.0, step=50.0, format="%.2f")
            if st.form_submit_button("Set Monthly Budget"):
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO budgets (user_id, category, monthly_limit, year_month) VALUES (%s, %s, %s, %s) ON CONFLICT(user_id, category, year_month) DO UPDATE SET monthly_limit=EXCLUDED.monthly_limit;", (uid, b_cat, b_limit, curr_month))
                conn.commit()
                c.close()
                conn.close()
                st.success("Budget Threshold Applied!")
                st.rerun()

        st.markdown("### 📊 Budget Progress (Current Month)")
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
                
                st.markdown(f"**{cat}** (Spent: {curr} {spent:,.2f} / Limit: {curr} {limit:,.2f})")
                st.progress(progress)
        else:
            st.info("No active budgets for this month.")

    # --- MODULE 6: NOTIFICATIONS INBOX ---
    elif choice == "🔔 Inbox":
        st.title("🔔 Messages & Alerts")
        
        conn = get_db_connection()
        c = conn.cursor()
        c.execute("UPDATE notifications SET is_read=TRUE WHERE user_id=%s AND is_read=FALSE;", (uid,))
        conn.commit()
        
        notifs = pd.read_sql_query("SELECT title as \"Title\", message as \"Message\", created_at as \"Timestamp\" FROM notifications WHERE user_id=%s ORDER BY created_at DESC", conn, params=(uid,))
        conn.close()

        if not notifs.empty:
            notifs["Timestamp"] = pd.to_datetime(notifs["Timestamp"]).dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(notifs, use_container_width=True, hide_index=True)
        else:
            st.info("Your inbox is empty.")

    # --- MODULE 7: ADMIN MASTER PANEL ---
    elif choice == "🔑 Admin Control Panel" and st.session_state.user['role'] == 'admin':
        st.title("🔑 Global Administration Center")
        tab1, tab2 = st.tabs(["🛡️ User Security Management", "📡 Broadcast System"])

        with tab1:
            conn = get_db_connection()
            users_df = pd.read_sql_query("SELECT id as \"ID\", username as \"User\", role as \"Role\", status as \"Status\" FROM users ORDER BY id ASC", conn)
            st.dataframe(users_df, use_container_width=True, hide_index=True)

            user_list = users_df[users_df['User'] != 'admin']['User'].tolist()
            if user_list:
                sel_u = st.selectbox("Select Target User", user_list)
                if st.button("🔄 Toggle Access (Active/Inactive)"):
                    c = conn.cursor()
                    c.execute("SELECT status FROM users WHERE username=%s;", (sel_u,))
                    curr_s = c.fetchone()[0]
                    nxt_s = 'inactive' if curr_s == 'active' else 'active'
                    c.execute("UPDATE users SET status=%s WHERE username=%s;", (nxt_s, sel_u))
                    conn.commit()
                    st.success(f"System Access for '{sel_u}' shifted to {nxt_s.upper()}")
                    st.rerun()
            conn.close()

        with tab2:
            with st.form("broadcast_form"):
                b_title = st.text_input("Push Alert Title")
                b_msg = st.text_area("Alert Payload (Message)")
                if st.form_submit_button("📡 Broadcast to All Nodes"):
                    if b_title and b_msg:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("SELECT id FROM users;")
                        for u in c.fetchall():
                            c.execute("INSERT INTO notifications (user_id, title, message) VALUES (%s, %s, %s);", (u[0], b_title, b_msg))
                        conn.commit()
                        conn.close()
                        st.success("Global Push Notification Deployed.")
                    else:
                        st.warning("Payload cannot be empty.")
