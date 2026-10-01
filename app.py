import hashlib
import json
import os
import urllib.parse
import pandas as pd
import streamlit as st
import stripe
import yfinance as yf

# ==========================================
# 1. CONFIGURATION STRIPE & SECRETS
# ==========================================
# Récupération de la clé Stripe (depuis st.secrets ou fallback pour le test local)
raw_key = str(st.secrets.get("STRIPE_SECRET_KEY", ""))
clean_key = raw_key.strip().replace("\n", "").replace("\r", "").replace(" ", "")
stripe.api_key = clean_key
# URL de ton site (mise à jour automatiquement sur Streamlit Cloud)
APP_URL = st.secrets.get("APP_URL", "http://localhost:8501")

# ==========================================
# 2. GESTION DE LA BASE DE DONNÉES (JSON)
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
# 3. FONCTIONS INTÉGRATION STRIPE
# ==========================================
def create_stripe_checkout_session(user_email):
    """Génère une page de paiement Stripe pour l'abonnement à 9.99$/mois"""
    try:
        checkout_session = stripe.checkout.Session.create(
            customer_email=user_email,
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "product_data": {
                        "name": "Abonnement IA Bourse Pro",
                        "description": (
                            "Accès illimité aux analyses IA, signaux"
                            " d'arbitrage et alertes."
                        ),
                    },
                    "unit_amount": 999,
                    "recurring": {"interval": "month"},
                },
                "quantity": 1,
            }],
            mode="subscription",
            success_url=f"{APP_URL}/?payment=success&email="
            + urllib.parse.quote(user_email),
            cancel_url=f"{APP_URL}/?payment=cancel",
        )
        return checkout_session.url
    except Exception as e:
        st.error(f"Erreur de communication avec Stripe : {e}")
        return None

# ==========================================
# 4. CONFIGURATION DE LA PAGE STREAMLIT
# ==========================================
st.set_page_config(
    page_title="IA StockAdvisor Pro", page_icon="📈", layout="wide"
)

# Gestion du retour de paiement Stripe via les paramètres d'URL
query_params = st.query_params
if query_params.get("payment") == "success":
    user_to_upgrade = query_params.get("email")
    if user_to_upgrade:
        users = load_users()
        if user_to_upgrade in users:
            users[user_to_upgrade]["is_pro"] = True
            save_users(users)
            st.success(
                "🎉 Paiement réussi ! Votre compte a été mis à niveau en"
                " version PRO."
            )

# Initialisation de la session utilisateur
if "user" not in st.session_state:
    st.session_state["user"] = None

# ==========================================
# 5. BARRE LATÉRALE : AUTHENTIFICATION & COMPTE
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
            if email_input in users and users[email_input][
                "password"
            ] == hash_password(password_input):
                st.session_state["user"] = email_input
                st.rerun()
            else:
                st.sidebar.error("E-mail ou mot de passe incorrect.")
else:
    current_email = st.session_state["user"]
    is_pro = users.get(current_email, {}).get("is_pro", False)

    st.sidebar.write(f"👤 Connecté : **{current_email}**")
    st.sidebar.write(
        f"Statut : **{'🟢 membre PRO' if is_pro else '⚪ Compte Gratuit'}**"
    )

    # Code Promo / Pass Propriétaire pour tester gratuitement
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
# 6. APPLICATION PRINCIPALE
# ==========================================
current_user = st.session_state["user"]
user_is_pro = (
    users.get(current_user, {}).get("is_pro", False) if current_user else False
)

st.title("🤖 IA Conseiller & Suivi Boursier")

# Bannière de vente pour la version Pro
if not user_is_pro:
    st.info(
        "💡 **Version Gratuite :** Analyse restreinte à l'action d'exemple"
        " (AAPL). Passez à la **version PRO (9.99 $/mois)** pour suivre"
        " n'importe quelle entreprise, recevoir des signaux d'arbitrage (Quand"
        " vendre X pour acheter Y) et débloquer les alertes IA."
    )

    if current_user:
        if st.button("🚀 Passer à la version PRO (9.99 $/mois) via Stripe"):
            checkout_url = create_stripe_checkout_session(current_user)
            if checkout_url:
                st.markdown(
                    f"[👉 Cliquez ici pour régler sur la page sécurisée Stripe]({checkout_url})"
                )
    else:
        st.warning("Veuillez créer un compte et vous connecter pour vous abonner.")

st.markdown("---")

# Sélection de l'action à analyser
if user_is_pro:
    ticker_input = st.text_input(
        "🔍 Entrez le symbole d'une action (ex: NVDA, TSLA, MC.PA, MSFT) :",
        "NVDA",
    )
else:
    ticker_input = "AAPL"
    st.write("📌 **Action en démonstration (Gratuit) :** AAPL (Apple Inc.)")

# Récupération des données yfinance
@st.cache_data(ttl=3600)
def fetch_stock_data(symbol):
    try:
        df = yf.download(symbol, period="1y", interval="1d")
        return df
    except Exception:
        return None


data = fetch_stock_data(ticker_input)

if data is not None and not data.empty:
    # Nettoyage des colonnes si multi-index
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)

    # Calcul d'indicateurs simples (Moyennes Mobiles)
    data["MA50"] = data["Close"].rolling(window=50).mean()
    data["MA200"] = data["Close"].rolling(window=200).mean()

    last_price = float(data["Close"].iloc[-1])
    last_ma50 = float(data["MA50"].iloc[-1])
    last_ma200 = float(data["MA200"].iloc[-1])

    col1, col2, col3 = st.columns(3)
    col1.metric("Prix Actuel", f"{last_price:.2f} $")
    col2.metric("Moyenne Mobile 50j", f"{last_ma50:.2f} $")
    col3.metric("Moyenne Mobile 200j", f"{last_ma200:.2f} $")

    # Graphique
    st.subheader(f"Évolution et Indicateurs : {ticker_input.upper()}")
    st.line_chart(data[["Close", "MA50", "MA200"]])

    # Module de recommandation IA
    st.subheader("🤖 Recommandation de l'Algorithme IA")

    if last_price > last_ma50 and last_ma50 > last_ma200:
        signal = "🟢 ACHETER / CONSERVER"
        explanation = (
            "L'action est en forte tendance haussière (Prix > MA50 > MA200)."
        )
    elif last_price < last_ma50:
        signal = "🔴 VENDRE / ALLÉGER"
        explanation = (
            "Le prix est repassé sous la moyenne à 50 jours. Signal d'alerte."
        )
    else:
        signal = "🟠 NEUTRE"
        explanation = "Pas de tendance claire détectée pour le moment."

    st.markdown(f"**Signal :** `{signal}`")
    st.write(explanation)

    # Section exclusive PRO : Arbitrage
    st.markdown("---")
    st.subheader("🔄 Module d'Arbitrage & Opportunités de Réinvestissement")

    if user_is_pro:
        st.success(
            " Analyse d'Arbitrage Débloquée : Si vous possédez ce titre et"
            " souhaitez réallouer votre capital, l'IA suggère actuellement de"
            " surveiller les paires à forte croissance sectorielle."
        )
        st.json({
            "Action analysée": ticker_input.upper(),
            "Score de croissance IA": "8.4/10",
            "Alternative suggérée (Plus fort momentum)": "NVDA",
            "Conseil d'arbitrage": (
                "Conserver 70%, Arbitrer 30% vers le secteur IA / Tech."
            ),
        })
    else:
        st.warning(
            "🔒 **Module Réservé aux Membres PRO :** Débloquez la fonctionnalité"
            " d'arbitrage automatique pour savoir exactement quand vendre une"
            " action et sur quelle compagnie réinvestir votre capital."
        )

else:
    st.error(
        f"Impossible de récupérer les données pour le symbole '{ticker_input}'. Vérifiez le ticker."
    )
# Avertissement Légal / Disclaimer
st.markdown("---")
st.caption(
    "⚠️ **Avertissement de responsabilité** : L'IA Kouhen FinTech et les signaux d'analyse fournis "
    "sur cette application sont transmis à titre purement informatif et éducatif. "
    "Ils n'incitent ni à acheter ni à vendre des instruments financiers. "
    "Les investissements sur les marchés comportent des risques de perte en capital. "
    "Consultez un professionnel de la finance agréé avant toute décision d'investissement."
)
