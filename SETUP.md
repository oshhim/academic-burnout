# Run EMPath+ on Mac or Windows

You run two parts:

- **Backend** (Python) on your computer
- **Mobile app** (Expo) on your phone

Your phone and computer must be on the **same Wi-Fi**.

---

## 1. Install these once

| Tool | Mac | Windows |
|---|---|---|
| **Python 3.12** (exactly 3.12) | `brew install python@3.12` | Download "Python 3.12 – Windows 64-bit" from [python.org](https://www.python.org/downloads/) and tick **Add to PATH** |
| **Node.js 20+** | `brew install node` | Download the LTS version from [nodejs.org](https://nodejs.org/) |
| **Git** | `brew install git` | Download from [git-scm.com](https://git-scm.com/) |
| **Expo Go** (on your phone) | App Store / Google Play | App Store / Google Play |

---

## 2. Get the code

```bash
git clone https://github.com/oshhim/academic-burnout.git
cd academic-burnout
```

> The repository is private: you need access to `oshhim/academic-burnout`.

---

## 3. Set up the backend (first time only)

**Mac** (Terminal):

```bash
cd backend
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-tested.txt
cp .env.example .env
python -m alembic upgrade head
```

**Windows** (Command Prompt):

```bat
cd backend
py -3.12 -m venv .venv
.venv\Scripts\activate.bat
python -m pip install -r requirements-tested.txt
copy .env.example .env
python -m alembic upgrade head
```

**Optional – real camera and microphone:** open `backend/.env` and change

```
ENABLE_RESEARCH_MODE=false
```

to

```
ENABLE_RESEARCH_MODE=true
```

---

## 4. Start the backend (every time)

**Mac:**

```bash
cd backend
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

**Windows:**

```bat
cd backend
.venv\Scripts\activate.bat
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Keep this window open. To check it works, open <http://127.0.0.1:8000/health> — it should show `"status":"ok"`.

---

## 5. Find your computer's IP address

| Mac | Windows |
|---|---|
| `ipconfig getifaddr en0` | `ipconfig` → look for **IPv4 Address** under Wi-Fi |

You'll get something like `192.168.1.246`. Your backend address is then:

```
http://192.168.1.246:8000
```

> The IP can change after your Wi-Fi reconnects. Check it again if the app stops connecting.

---

## 6. Start the mobile app (open a second terminal window)

Same on Mac and Windows:

```bash
cd mobile
npm install          # first time only
npx expo start -c
```

A **QR code** appears in the terminal.

---

## 7. Open the app on your phone

1. **iPhone:** scan the QR code with the Camera app. **Android:** scan it in Expo Go.
2. Go through the welcome slides and tap **Get started**.
3. On **Profile**, check the **Backend URL** shows your IP from step 5 (e.g. `http://192.168.1.246:8000`). Tap **Edit** to change it.
4. Turn on **I consent** and tap **Connect and register**.
5. *(Camera and microphone)* Choose **Real capture**, give consent, and tap **Enable real capture**. This needs the optional `.env` change in step 3.

---

## 8. Stop everything

Press **Ctrl+C** in each terminal window. Your data stays saved in `backend/data/empath.db`.

---

## Problems?

| Problem | Fix |
|---|---|
| "Cannot reach the backend" | Is the backend running? Is the phone on the same Wi-Fi? Check the IP (it can change) in **Profile → Edit**. |
| Phone still can't connect (Mac) | Allow incoming connections for **Python** in System Settings → Network → Firewall |
| Phone still can't connect (Windows) | When Windows asks about Python, click **Allow access** (tick **Private networks**) |
| "Project is incompatible with this version of Expo Go" | The app uses **Expo SDK 57**. Update Expo Go, or move the project to the SDK version your Expo Go supports. |
| `python3.12` / `py -3.12` not found | Install Python 3.12 (step 1). Other versions don't work with the trained models. |
| `No module named ...` | Activate the environment first (`source .venv/bin/activate` or `.venv\Scripts\activate.bat`) |
| Camera or microphone refused | Set `ENABLE_RESEARCH_MODE=true` in `backend/.env` and restart the backend |

---

More detail: [backend/README.md](backend/README.md) · [mobile/README.md](mobile/README.md)
