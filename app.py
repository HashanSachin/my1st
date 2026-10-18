import streamlit as st
import psycopg2
from psycopg2.extras import RealDictCursor
import pandas as pd
import plotly.express as px
import hashlib
import uuid
from datetime import datetime

# ==========================================
# 1. APP CONFIGURATION & MAX-LEVEL CSS
# ==========================================
st.set_page_config(page_title="FinMaster Pro", layout="centered", initial_sidebar_state="collapsed")

# Advanced CSS to force Mobile App look and override Dark Mode bugs
st.markdown("""
    <style>
    /* Clean App Background */
    .stApp { background-color: #F8FAFC; font-family: 'Segoe UI', Roboto, sans-serif; }
    
    /* Hide Streamlit Default UI */
    #MainMenu, footer, header, [data-testid="collapsedControl"] {visibility: hidden; display: none;}
    
    /* Force Text Colors to always be visible (Bypass Dark Mode issues) */
    h1, h2, h3, h4, p, label, .stMarkdown, div[data-testid="stText"] { color: #0F172A !important; }
    
    /* Custom Premium Buttons */
    div.stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #0284C7 0%, #2563EB 100%) !important;
        color: white !important;
        border: none;
        border-radius: 12px;
        min-height: 55px;
        font-size: 16px;
        font-weight: 600;
        box-shadow: 0 4px 10px rgba(37, 99, 235, 0.2) !important;
        transition: 0.2s;
    }
    div.stButton > button[kind="primary"]:active { transform: scale(0.97); }
    
    /* Secondary Action Buttons */
    div.stButton > button[kind="secondary"] {
        background: #E2E8F0 !important;
        color: #1E293B !important;
        border: none;
        border-radius: 12px;
        min-height: 55px;
        font-weight: 600;
    }
    
    /* Metric Cards */
    div[data-testid="metric-container"] {
        background: #ffffff;
        padding: 20px;
        border-radius: 16px;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        border: 1px solid #E2E8F0;
    }
    div[data-testid="metric-container"] label { color: #64748B !important; }
    div[data-testid="metric-container"] div { color: #0F172A !important; font-size: 32px !important; font-weight: 700 !important;}
    
    /* Inputs & Forms */
    .stTextInput>div>div>input, .stSelectbox>div>div>div, .stNumberInput>div>div>input { 
        border-radius: 10px; border: 1px solid #CBD5E1; color: #0F172A !important; background: #ffffff !important; 
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 2. STATE & DATABASE OPTIMIZATION (SPEED UP)
# ==========================================
if 'user_id' not in st.session_state:
    st.session_state.update({'user_id': None, 'role': None, 'username': None, 'current_page': 'Home'})

def change_page(page_name):
    st.session_state.current_page = page_name

# Cache Database connection to stop lag on every button click
@st.cache_resource
def init_connection():
    return psycopg2.connect(st.secrets["CLOUD_DB_URL"], cursor_factory=RealDictCursor)

def run_query(query, params=(), fetch=False, fetch_all=False, commit=True):
    try:
        conn = init_connection()
        if conn.closed:
            conn = psycopg2.connect(st.secrets["CLOUD_DB_URL"], cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute(query, params)
        result = None
        if fetch: result = cur.fetchone()
        elif fetch_all: result = cur.fetchall()
        if commit: conn.commit()
        cur.close()
        return result
    except Exception as e:
        st.error(f"DB Error: {e}")
        st.cache_resource.clear()
        return None

def hash_password(password):
    return hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), st.secrets["SECRET_SALT"].encode('utf-8'), 100000).hex()

# ==========================================
# 3. SCHEMA (DATABASE TABLES)
# ==========================================
def init_db():
    schema = """
    CREATE TABLE IF NOT EXISTS users (id SERIAL PRIMARY KEY, username VARCHAR(50) UNIQUE NOT NULL, password_hash VARCHAR(255) NOT NULL, role VARCHAR(20) DEFAULT 'user', status VARCHAR(20) DEFAULT 'active', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
    CREATE TABLE IF NOT EXISTS product_keys (id SERIAL PRIMARY KEY, key_code VARCHAR(50) UNIQUE NOT NULL, is_used BOOLEAN DEFAULT FALSE, used_by VARCHAR(50));
    CREATE TABLE IF NOT EXISTS accounts (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, name VARCHAR(100) NOT NULL, type VARCHAR(50), balance NUMERIC DEFAULT 0.0);
    CREATE TABLE IF NOT EXISTS transactions (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, account_id INTEGER REFERENCES accounts(id) ON DELETE CASCADE, type VARCHAR(20), amount NUMERIC, category VARCHAR(50), description TEXT, date DATE);
    CREATE TABLE IF NOT EXISTS notifications (id SERIAL PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE CASCADE, message TEXT, is_read BOOLEAN DEFAULT FALSE);
    """
    run_query(schema)
    if not run_query("SELECT id FROM users WHERE username = 'admin'", fetch=True, commit=False):
        run_query("INSERT INTO users (username, password_hash, role) VALUES (%s, %s, 'admin')", ('admin', hash_password('admin123')))

# ==========================================
# 4. AUTHENTICATION & LOGIN
# ==========================================
def render_auth():
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("<h1 style='text-align: center; color: #0284C7 !important;'>FinMaster Pro</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center; color: #64748B !important;'>Secure Web App Experience</p><hr>", unsafe_allow_html=True)
    
    t1, t2 = st.tabs(["🔒 Sign In", "📝 Register"])
    
    with t1:
        username = st.text_input("Username", key="log_user")
        password = st.text_input("Password", type="password", key="log_pass")
        if st.button("Login to Dashboard", type="primary", use_container_width=True):
            user = run_query("SELECT * FROM users WHERE username = %s AND password_hash = %s", (username, hash_password(password)), fetch=True)
            if user and user['status'] == 'active':
                st.session_state.update({'user_id': user['id'], 'username': user['username'], 'role': user['role'], 'current_page': 'Home'})
                st.rerun()
            else:
                st.error("Invalid credentials or suspended account.")
        st.info("Forgot Password? Please contact the Administrator.")

    with t2:
        st.warning("Registration requires a 1-Time Product Key.")
        new_user = st.text_input("Choose Username")
        new_pass = st.text_input("Choose Password", type="password")
        prod_key = st.text_input("Enter Product Key")
        if st.button("Complete Registration", type="primary", use_container_width=True):
            if new_user and new_pass and prod_key:
                if run_query("SELECT id FROM product_keys WHERE key_code = %s AND is_used = FALSE", (prod_key,), fetch=True):
                    if not run_query("SELECT id FROM users WHERE username = %s", (new_user,), fetch=True):
                        run_query("INSERT INTO users (username, password_hash) VALUES (%s, %s)", (new_user, hash_password(new_pass)))
                        run_query("UPDATE product_keys SET is_used = TRUE, used_by = %s WHERE key_code = %s", (new_user, prod_key))
                        admin = run_query("SELECT id FROM users WHERE role = 'admin' LIMIT 1", fetch=True)
                        if admin: 
                            run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (admin['id'], f"🚨 New user registered: {new_user}"))
                        st.success("Success! You can now log in.")
                    else: st.error("Username already taken.")
                else: st.error("Invalid or used Product Key.")
            else: st.warning("Please fill all fields.")

# ==========================================
# 5. CORE APP SCREENS
# ==========================================
def render_header(title):
    c1, c2 = st.columns([1, 4])
    with c1: st.button("❮ Back", on_click=change_page, args=('Home',), type="secondary", use_container_width=True)
    with c2: st.markdown(f"<h3 style='margin-top: 10px;'>{title}</h3>", unsafe_allow_html=True)
    st.markdown("<hr style='margin-top: 0px;'>", unsafe_allow_html=True)

def render_home(u_id):
    st.markdown(f"<h2>Hello, <span style='color:#0284C7 !important;'>{st.session_state.username}</span> 👋</h2>", unsafe_allow_html=True)
    
    unread = run_query("SELECT COUNT(*) as c FROM notifications WHERE (user_id = %s OR user_id IS NULL) AND is_read = FALSE", (u_id,), fetch=True)
    if unread and unread['c'] > 0: st.warning(f"You have {unread['c']} unread notification(s)!")
    
    accounts = run_query("SELECT name, balance FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    total_balance = sum(a['balance'] for a in accounts) if accounts else 0.0
    st.metric("Total Net Worth", f"${total_balance:,.2f}")
    
    if accounts and total_balance > 0:
        df = pd.DataFrame(accounts)
        fig = px.pie(df, values='balance', names='name', hole=0.6, color_discrete_sequence=px.colors.sequential.Teal)
        fig.update_layout(showlegend=False, margin=dict(t=10, b=10, l=10, r=10), height=200, paper_bgcolor='rgba(0,0,0,0)')
        fig.add_annotation(text="Assets", x=0.5, y=0.5, font=dict(color="#0F172A", size=20), showarrow=False)
        st.plotly_chart(fig, use_container_width=True, config={'displayModeBar': False})
    
    st.markdown("### Menu")
    g1, g2 = st.columns(2)
    with g1:
        st.button("💼 Accounts", on_click=change_page, args=('Accounts',), type="primary", use_container_width=True)
        st.button("🔔 Notifications", on_click=change_page, args=('Notifications',), type="primary", use_container_width=True)
    with g2:
        st.button("💸 Transactions", on_click=change_page, args=('Transactions',), type="primary", use_container_width=True)
        st.button("⚙️ Settings", on_click=change_page, args=('Settings',), type="primary", use_container_width=True)
        
    if st.session_state.role == 'admin':
        st.markdown("<br>", unsafe_allow_html=True)
        st.button("🛡️ Master Admin Panel", on_click=change_page, args=('Admin',), type="secondary", use_container_width=True)
        
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🚪 Log Out", type="secondary", use_container_width=True):
        st.session_state.clear()
        st.rerun()

def render_accounts(u_id):
    render_header("Manage Accounts")
    
    with st.expander("➕ Add New Account", expanded=True):
        a_name = st.text_input("Account Name")
        a_type = st.selectbox("Type", ["Bank", "Cash", "Investment", "Crypto"])
        a_bal = st.number_input("Starting Balance", value=0.0)
        if st.button("Save Account", type="primary", use_container_width=True):
            run_query("INSERT INTO accounts (user_id, name, type, balance) VALUES (%s, %s, %s, %s)", (u_id, a_name, a_type, a_bal))
            st.rerun()

    st.markdown("### Your Accounts")
    accounts = run_query("SELECT id, name, type, balance FROM accounts WHERE user_id = %s ORDER BY balance DESC", (u_id,), fetch_all=True)
    if accounts:
        for acc in accounts:
            with st.container():
                st.markdown(f"**{acc['name']}** ({acc['type']})  \n 💰 **${acc['balance']:,.2f}**")
                if st.button(f"Delete '{acc['name']}'", key=f"del_{acc['id']}", type="secondary", use_container_width=True):
                    run_query("DELETE FROM accounts WHERE id = %s", (acc['id'],))
                    st.rerun()
                st.markdown("---")
    else: st.info("No accounts found.")

def render_transactions(u_id):
    render_header("Transactions")
    accounts = run_query("SELECT id, name FROM accounts WHERE user_id = %s", (u_id,), fetch_all=True)
    if not accounts:
        st.warning("Add an account first before creating transactions.")
        return

    acc_dict = {a['name']: a['id'] for a in accounts}
    
    with st.expander("➕ Add Transaction", expanded=True):
        t_acc = st.selectbox("Select Account", list(acc_dict.keys()))
        t_type = st.selectbox("Type", ["Income", "Expense"])
        t_amt = st.number_input("Amount", min_value=0.01)
        t_cat = st.text_input("Category (e.g. Salary, Food)")
        t_date = st.date_input("Date")
        if st.button("Save Record", type="primary", use_container_width=True):
            acc_id = acc_dict[t_acc]
            run_query("INSERT INTO transactions (user_id, account_id, type, amount, category, date) VALUES (%s, %s, %s, %s, %s, %s)",
                      (u_id, acc_id, t_type, t_amt, t_cat, t_date))
            mod = t_amt if t_type == 'Income' else -t_amt
            run_query("UPDATE accounts SET balance = balance + %s WHERE id = %s", (mod, acc_id))
            st.rerun()

    st.markdown("### Edit or Delete Records")
    txns = run_query("SELECT t.id, a.name as acc, t.date, t.type, t.amount, t.category FROM transactions t JOIN accounts a ON t.account_id = a.id WHERE t.user_id = %s ORDER BY t.id DESC LIMIT 50", (u_id,), fetch_all=True)
    if txns:
        # Create a dropdown to select a transaction to edit
        t_id = st.selectbox("Select Record to Modify", [t['id'] for t in txns], format_func=lambda x: f"{next(t['date'] for t in txns if t['id']==x)} | {next(t['type'] for t in txns if t['id']==x)} | ${next(t['amount'] for t in txns if t['id']==x)}")
        curr = next(t for t in txns if t['id'] == t_id)
        
        st.markdown("Update Values:")
        e_type = st.selectbox("Update Type", ["Income", "Expense"], index=0 if curr['type']=='Income' else 1, key="e_t")
        e_amt = st.number_input("Update Amount", value=float(curr['amount']), key="e_a")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("Update Changes", type="primary", use_container_width=True):
                # Update logic (doesn't auto adjust balance here for safety on complex edits, just logs)
                run_query("UPDATE transactions SET type=%s, amount=%s WHERE id=%s", (e_type, e_amt, t_id))
                st.success("Updated Successfully!")
                st.rerun()
        with c2:
            if st.button("Delete Record", type="secondary", use_container_width=True):
                run_query("DELETE FROM transactions WHERE id=%s", (t_id,))
                st.rerun()

def render_settings(u_id):
    render_header("User Settings")
    
    st.markdown("**1. Change Username**")
    new_u = st.text_input("Enter New Username")
    if st.button("Update Username", type="primary", use_container_width=True):
        if run_query("SELECT id FROM users WHERE username = %s", (new_u,), fetch=True): st.error("Username already taken.")
        else:
            run_query("UPDATE users SET username = %s WHERE id = %s", (new_u, u_id))
            st.session_state.username = new_u
            st.success("Username Changed Successfully.")
            
    st.markdown("<br>**2. Change Password**", unsafe_allow_html=True)
    new_p = st.text_input("Enter New Password", type="password")
    if st.button("Update Password", type="primary", use_container_width=True):
        run_query("UPDATE users SET password_hash = %s WHERE id = %s", (hash_password(new_p), u_id))
        st.success("Password Changed Successfully.")

def render_notifications(u_id):
    render_header("Notifications")
    # Using ID to sort instead of date to prevent database schema errors
    notifs = run_query("SELECT * FROM notifications WHERE user_id = %s OR user_id IS NULL ORDER BY id DESC", (u_id,), fetch_all=True)
    
    if notifs:
        if st.button("Mark All as Read", type="primary", use_container_width=True):
            run_query("UPDATE notifications SET is_read = TRUE WHERE user_id = %s OR user_id IS NULL", (u_id,))
            st.rerun()
        st.markdown("<br>", unsafe_allow_html=True)
        for n in notifs:
            bg_color = "#ffffff" if n['is_read'] else "#F1F5F9"
            icon = "✅" if n['is_read'] else "🔔"
            st.markdown(f"<div style='background:{bg_color}; padding:15px; border-radius:10px; border:1px solid #E2E8F0; margin-bottom:10px;'>"
                        f"<strong>{icon} Alert</strong><br>{n['message']}</div>", unsafe_allow_html=True)
    else: st.info("You have no notifications.")

def render_admin():
    render_header("Admin Panel")
    
    with st.expander("🔑 Generate 1-Time Product Keys", expanded=True):
        if st.button("Create New Key", type="primary", use_container_width=True):
            new_key = "KEY-" + str(uuid.uuid4()).split('-')[0].upper()
            run_query("INSERT INTO product_keys (key_code) VALUES (%s)", (new_key,))
            st.success(f"Generated Key: {new_key}")
        keys = run_query("SELECT key_code, is_used, used_by FROM product_keys ORDER BY id DESC LIMIT 10", fetch_all=True)
        if keys: st.dataframe(pd.DataFrame(keys), use_container_width=True)

    with st.expander("📢 Send Individual / Broadcast Alerts"):
        users = run_query("SELECT id, username FROM users", fetch_all=True)
        usr_dict = {"Broadcast (All Users)": None}
        for u in users: usr_dict[f"{u['username']} (ID: {u['id']})"] = u['id']
        
        target = st.selectbox("Select Recipient", list(usr_dict.keys()))
        msg = st.text_area("Notification Message")
        if st.button("Send Alert", type="primary", use_container_width=True):
            run_query("INSERT INTO notifications (user_id, message) VALUES (%s, %s)", (usr_dict[target], msg))
            st.success("Alert Sent Successfully.")

    with st.expander("👤 Delete Users (Danger Zone)"):
        df_u = pd.DataFrame(run_query("SELECT id, username, role FROM users", fetch_all=True))
        st.dataframe(df_u, use_container_width=True)
        del_id = st.selectbox("Select User ID to Terminate", df_u[df_u['role'] != 'admin']['id'].tolist())
        if st.button("Permanently Delete User", type="secondary", use_container_width=True):
            run_query("DELETE FROM users WHERE id = %s", (del_id,))
            st.rerun()

# ==========================================
# 6. APP EXECUTION
# ==========================================
def main():
    init_db()
    if not st.session_state.user_id: render_auth()
    else:
        page = st.session_state.current_page
        if page == 'Home': render_home(st.session_state.user_id)
        elif page == 'Accounts': render_accounts(st.session_state.user_id)
        elif page == 'Transactions': render_transactions(st.session_state.user_id)
        elif page == 'Notifications': render_notifications(st.session_state.user_id)
        elif page == 'Settings': render_settings(st.session_state.user_id)
        elif page == 'Admin' and st.session_state.role == 'admin': render_admin()

if __name__ == "__main__": main()
