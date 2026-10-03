import hashlib
import json
import os
import urllib.parse
import pandas as pd
import streamlit as st
import stripe
import yfinance as yf
import sqlite3
from datetime import datetime, timedelta, timezone
from google import genai

# ==========================================
# 1. INITIALISATION BDD & FONCTIONS FAVORIS
# ==========================================
def init_db():
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            added_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def add_favorite(ticker):
    conn = sqlite3.connect("portfolio.db")
    cursor = conn.cursor()
    today_str = datetime.now().strftime("%Y-%m-%d")
    try:
        cursor.execute(
            "INSERT INTO watchlist (ticker, added_date) VALUES (?, ?)",
            (ticker.upper(), today_str)
        )
        conn.commit()
        st.toast(f"⭐ {ticker.upper()} ajouté aux favoris !", icon="⭐")
    except sqlite3.IntegrityError:
        st.toast(f"⚠️ {ticker.upper()} est déjà dans vos favoris.", icon="⚠️")
    finally:
        conn.close()

init_db()

# ==========================================
# 2. CONFIGURATION STRIPE & GEMINI SECRETS
# ==========================================
raw_key = str(st.secrets.get("STRIPE_SECRET_KEY", ""))
clean_key = raw_key.strip().replace("\n", "").replace("\r", "").replace(" ", "")
stripe.api_key = clean_key
APP_URL = st.secrets.get("APP_URL", "http://localhost:8501")

# Initialisation du client Gemini API
gemini_key = st.secrets.get("GEMINI_API_KEY", "")
client = genai.Client(api_key=gemini_key) if gemini_key else None

# ==========================================
# 3. GESTION DE LA BASE DE DONNÉES (JSON)
# ==========================================
DB_FILE = "users_db.json"

def load_users():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(DB_FILE, "w") as f:
        json.dump(users, f, indent=4)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ==========================================
# 4. FONCTIONS INTÉGRATION STRIPE
# ==========================================
def create_stripe_checkout_session(user_email):
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=user_email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Abonnement IA Bourse Pro",
                        "description": "Accès illimité aux analyses IA, signaux d'arbitrage et assistant personnel.",
                    },
                    "unit_amount": 999,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{APP_URL}/?payment=success&email=" + urllib.parse.quote(user_email),
            cancel_url=f"{APP_URL}/?payment=cancel",
        )
        return checkout_session.url
    except Exception as e:
        st.error(f"Erreur de communication avec Stripe : {e}")
        return None

# ==========================================
# 5. CONFIGURATION DE LA PAGE STREAMLIT
# ==========================================
st.set_page_config(page_title="IA StockAdvisor Pro", page_icon="📈", layout="wide")

query_params = st.query_params
if query_params.get("payment") == "success":
    user_to_upgrade = query_params.get("email")
    if user_to_upgrade:
        users = load_users()
        if user_to_upgrade in users:
            users[user_to_upgrade]["is_pro"] = True
            save_users(users)
            st.success("🎉 Paiement réussi ! Votre compte a été mis à niveau en version PRO.")

if "user" not in st.session_state:
    st.session_state["user"] = None

# ==========================================
# 6. BARRE LATÉRALE : AUTHENTIFICATION
# ==========================================
st.sidebar.title("📈 StockAdvisor IA")
users = load_users()

if st.session_state["user"] is None:
    st.sidebar.subheader("Connexion / Inscription")
    menu = st.sidebar.radio("Option", ["Se connecter", "Créer un compte"])
    email_input = st.sidebar.text_input("Adresse E-mail").lower().strip()
    password_input = st.sidebar.text_input("Mot de passe", type="password")

    if menu == "Créer un compte":
        if st.sidebar.button("S'inscrire"):
            if email_input in users:
                st.sidebar.error("Un compte existe déjà avec cet email.")
            elif email_input and password_input:
                users[email_input] = {
                    "password": hash_password(password_input),
                    "is_pro": False,
                }
                save_users(users)
                st.sidebar.success("Compte créé ! Connectez-vous.")
            else:
                st.sidebar.warning("Veuillez remplir tous les champs.")

    elif menu == "Se connecter":
        if st.sidebar.button("Connexion"):
            if email_input in users and users[email_input]["password"] == hash_password(password_input):
                st.session_state["user"] = email_input
                st.rerun()
            else:
                st.sidebar.error("E-mail ou mot de passe incorrect.")
else:
    current_email = st.session_state["user"]
    is_pro = users.get(current_email, {}).get("is_pro", False)

    st.sidebar.write(f"👤 Connecté : **{current_email}**")
    st.sidebar.write(f"Statut : **{'🟢 membre PRO' if is_pro else '⚪ Compte Gratuit'}**")

    if not is_pro:
        promo_code = st.sidebar.text_input("Code Promo / Admin", type="password")
        if promo_code in ["OWNER100", "ADMIN2026"]:
            users[current_email]["is_pro"] = True
            save_users(users)
            st.sidebar.success("Accès Administrateur Débloqué !")
            st.rerun()

    if st.sidebar.button("Déconnexion"):
        st.session_state["user"] = None
        st.rerun()

# ==========================================
# 7. APPLICATION PRINCIPALE
# ==========================================
current_user = st.session_state["user"]
user_is_pro = users.get(current_user, {}).get("is_pro", False) if current_user else False

st.title("🤖 IA Conseiller & Suivi Boursier")

if not user_is_pro:
    st.info(
        "💡 **Version Gratuite :** Analyse restreinte à l'action d'exemple (AAPL). "
        "Passez à la **version PRO (9.99 $/mois)** pour suivre n'importe quelle entreprise et débloquer l'assistant IA."
    )
    if current_user:
        if st.button("🚀 Passer à la version PRO (9.99 $/mois) via Stripe"):
            checkout_url = create_stripe_checkout_session(current_user)
            if checkout_url:
                st.markdown(f"[👉 Cliquez ici pour régler sur la page sécurisée Stripe]({checkout_url})")
    else:
        st.warning("Veuillez créer un compte et vous connecter pour vous abonner.")

st.markdown("---")

if user_is_pro:
    ticker_input = st.text_input("🔍 Entrez le symbole d'une action (ex: NVDA, TSLA, MC.PA, MSFT, LLY, AMZN) :", "NVDA")
else:
    ticker_input = "AAPL"
    st.write("📌 **Action en démonstration (Gratuit) :** AAPL (Apple Inc.)")

@st.cache_data(ttl=3600)
def fetch_stock_data(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1d")
        return df
    except Exception:
        return None

data = fetch_stock_data(ticker_input)
ticker = yf.Ticker(ticker_input)

# Variables de stock
signal = "N/A"
explanation = "Données insuffisantes pour analyser ce titre."
last_price, last_ma50, last_ma200 = None, None, None

if ticker_input.endswith(".MA"):
    currency = "DH"
elif ticker_input.endswith(".DE") or ticker_input.endswith(".PA"):
    currency = "€"
else:
    currency = "$"

# Statut du marché
try:
    now_utc = datetime.now(timezone.utc)
    if ticker_input.endswith(".DE") or ticker_input.endswith(".PA"):
        open_hour, close_hour = 7, 15
        close_minute = 30
        tz_label = "Europe/Paris/Berlin"
    else:
        open_hour, close_hour = 13, 20
        close_minute = 0
        tz_label = "US/Eastern"

    is_weekend = now_utc.weekday() >= 5
    open_time = now_utc.replace(hour=open_hour, minute=30 if open_hour == 13 else 0, second=0, microsecond=0)
    close_time = now_utc.replace(hour=open_hour, minute=close_minute, second=0, microsecond=0)

    is_open = (not is_weekend) and (open_time <= now_utc <= close_time)

    if is_open:
        st.success(f"🟢 **Marché Ouvert** ({tz_label})")
    else:
        next_open = open_time
        if now_utc > close_time:
            next_open += timedelta(days=1)
        while next_open.weekday() >= 5:
            next_open += timedelta(days=1)
        
        diff = next_open - now_utc
        hours, remainder = divmod(diff.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        st.warning(f"🔴 **Marché Fermé** | Ouvre dans {diff.days * 24 + hours}h {minutes}min")
except Exception as e:
    st.info(f"Erreur marché : {e}")

if data is not None and not data.empty:
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    data["MA50"] = data["Close"].rolling(window=50).mean()
    data["MA200"] = data["Close"].rolling(window=200).mean()

    try:
        last_price = float(ticker.fast_info['lastPrice'])
    except:
        try:
            last_price = float(data["Close"].dropna().iloc[-1])
        except:
            last_price = None

    try:
        last_ma50 = float(data["MA50"].dropna().iloc[-1])
        last_ma200 = float(data["MA200"].dropna().iloc[-1])
    except:
        last_ma50, last_ma200 = None, None

    col1, col2, col3 = st.columns(3)
    col1.metric("Prix Actuel", f"{last_price:.2f} {currency}" if last_price else "N/A")
    col2.metric("Moyenne Mobile 50j", f"{last_ma50:.2f} {currency}" if last_ma50 else "N/A")
    col3.metric("Moyenne Mobile 200j", f"{last_ma200:.2f} {currency}" if last_ma200 else "N/A")

    col_title, col_fav_btn = st.columns([3, 1])
    with col_title:
        st.subheader(f"Évolution et Indicateurs : {ticker_input.upper()}")
    with col_fav_btn:
        if st.button("⭐ Favori", key="btn_add_fav", use_container_width=True):
            add_favorite(ticker_input)

    st.line_chart(data[["Close", "MA50", "MA200"]])

    st.subheader("🤖 Recommandation de l'Algorithme IA")

    if last_price and last_ma50 and last_ma200:
        if last_price > last_ma50 and last_ma50 > last_ma200:
            signal = "🟢 ACHETER / CONSERVER"
            explanation = f"Tendances très positives pour {ticker_input.upper()} : le prix ({last_price:.2f} {currency}) est supérieur aux MM50 et MM200."
            st.success(f"**{signal}**\n\n{explanation}")
        elif last_price < last_ma50 and last_ma50 < last_ma200:
            signal = "🔴 VENDRE / ALLÉGER"
            explanation = f"Tendances baissières pour {ticker_input.upper()} : le cours est sous ses moyennes mobiles principales."
            st.error(f"**{signal}**\n\n{explanation}")
        else:
            signal = "🟠 NEUTRE / CONSOLIDATION"
            explanation = f"Signal mitigé pour {ticker_input.upper()} : phase d'attente ou de consolidation."
            st.warning(f"**{signal}**\n\n{explanation}")
    else:
        st.info(f"⚠️ {explanation}")

st.markdown(f"**Signal pour {ticker_input.upper()} :** {signal}")
st.caption(explanation)

st.markdown("---")

# ==========================================
# 8. MODULE CHATBOT IA & CONSEILS SUR-MESURE (RÉSERVÉ AUX MEMBRES PRO)
# ==========================================
st.subheader("💬 Assistant IA Financial Advisor")

if user_is_pro:
    st.write("Demandez à l'IA des idées d'actions à forte croissance, des analyses de secteurs ou des stratégies de gestion de risque.")

    if not client:
        st.warning("⚠️ Clé API Gemini manquante. Veuillez ajouter `GEMINI_API_KEY` dans vos secrets Streamlit.")
    else:
        if "messages" not in st.session_state:
            st.session_state.messages = [
                {
                    "role": "assistant",
                    "content": f"Bonjour ! Je suis votre conseiller financier IA. Je peux vous proposer des actions à forte croissance adaptées à votre budget, analyser **{ticker_input.upper()}** ou diversifier votre portefeuille. Que souhaitez-vous savoir ?"
                }
            ]

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if user_prompt := st.chat_input("Ex: Propose-moi 3 actions en pleine croissance en dehors des Big Tech..."):
            st.session_state.messages.append({"role": "user", "content": user_prompt})
            with st.chat_message("user"):
                st.markdown(user_prompt)

            system_instruction = f"""
            Tu es un analyste financier expert, neutre et très pédagogique au sein de StockAdvisor IA.
            Contexte de l'utilisateur :
            - Statut : Membre PRO
            - Action sélectionnée à l'écran : {ticker_input.upper()}
            - Prix de l'action : {last_price if last_price else 'Inconnu'} {currency}
            - Tendance actuelle : {signal}

            RÈGLES IMPORTANTES :
            1. Ne limite PAS tes recommandations à NVDA, AAPL ou MSFT. Explore divers secteurs (santé comme Eli Lilly/Novo Nordisk, semi-conducteurs, énergie verte, cybersécurité, fintech, et ETFs comme QQQ/SPY).
            2. Propose toujours des explications concrètes : pourquoi l'entreprise est en croissance (catalyseurs, résultats financiers, secteur porteur).
            3. Rappelle brièvement la gestion des risques (diversification, horizon de temps).
            4. Sois structuré avec des puces et un ton professionnel mais accessible.
            """

            full_prompt = f"{system_instruction}\n\nQuestion de l'utilisateur : {user_prompt}"

            with st.chat_message("assistant"):
                try:
                    response = client.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=full_prompt
                    )
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Erreur lors de la génération : {e}")
else:
    st.info("🔒 **Fonctionnalité réservée aux membres PRO**")
    st.write("L'assistant IA conversationnel permet de poser des questions personnalisées, d'obtenir des idées d'actions à fort potentiel et des analyses de portefeuilles.")
    if current_user:
        if st.button("🚀 Débloquer l'Assistant IA avec la version PRO (9.99 $/mois)"):
            checkout_url = create_stripe_checkout_session(current_user)
            if checkout_url:
                st.markdown(f"[👉 Cliquez ici pour procéder au paiement Stripe]({checkout_url})")
    else:
        st.warning("Veuillez vous connecter pour vous abonner et accéder à l'Assistant IA.")

st.markdown("---")
st.caption(
    "⚠️ **Avertissement de responsabilité** : L'IA Kouhen FinTech et les signaux d'analyse fournis "
    "sur cette application sont transmis à titre purement informatif et éducatif."
)
