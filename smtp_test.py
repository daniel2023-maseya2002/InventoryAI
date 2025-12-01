# smtp_test.py
import smtplib, os
from email.message import EmailMessage

HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
PORT = int(os.getenv("EMAIL_PORT", 587))
USER = os.getenv("EMAIL_HOST_USER", "")
PWD  = os.getenv("EMAIL_HOST_PASSWORD", "")
FROM = USER
TO   = ["your.receiving.email@example.com"]  # change to an address you control

msg = EmailMessage()
msg.set_content("SMTP test from python")
msg["Subject"] = "SMTP Test"
msg["From"] = FROM
msg["To"] = ", ".join(TO)

try:
    s = smtplib.SMTP(HOST, PORT, timeout=20)
    s.set_debuglevel(1)           # show SMTP protocol conversation
    s.ehlo()
    s.starttls()
    s.ehlo()
    s.login(USER, PWD)
    s.send_message(msg)
    s.quit()
    print("SENT OK")
except Exception as e:
    print("SMTP ERROR:", type(e), e)
