"""Plain-text and branded HTML versions of LyFind's one-time code emails."""
from email.message import EmailMessage
from html import escape


def code_email(recipient, code, *, subject, heading, intro, instructions, expiry, security_note):
    message = EmailMessage()
    message["Subject"] = subject
    message["To"] = recipient
    timing = f"Use it once within {expiry}."
    message.set_content(f"{intro}\n\n{code}\n\n{instructions} {timing}\n\n{security_note}")

    code_style = ("font-size:36px;letter-spacing:6px;" if len(code) == 6
                  else "font-size:17px;word-break:break-all;word-wrap:break-word;")
    message.add_alternative(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(subject)}</title>
</head>
<body style="margin:0;background-color:#f7f5ef;color:#2f282b;font-family:Arial,sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background-color:#f7f5ef;">
    <tr><td align="center" style="padding:32px 12px;">
      <table role="presentation" width="100%" cellspacing="0" cellpadding="0"
             style="max-width:520px;background-color:#fffefa;border:1px solid #e5dfd6;border-radius:16px;">
        <tr><td style="padding:23px 24px;background-color:#800020;border-radius:15px 15px 0 0;border-bottom:3px solid #d5b574;">
          <p style="margin:0;font-size:24px;font-weight:bold;color:#fffefa;">LyFind</p>
          <p style="margin:5px 0 0;color:#f0dbb4;font-size:12px;letter-spacing:1px;">CAMPUS LOST &amp; FOUND</p>
        </td></tr>
        <tr><td style="padding:26px 24px 24px;">
          <h1 style="margin:0 0 10px;color:#4e1422;font-size:25px;line-height:1.25;">{escape(heading)}</h1>
          <p style="margin:0 0 20px;font-size:15px;line-height:1.6;">{escape(intro)}</p>
          <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="table-layout:fixed;">
            <tr><td align="center" style="padding:19px 12px;background-color:#f6ecee;border:1px solid #e8d0d6;border-radius:12px;">
              <p style="margin:0 0 9px;color:#650019;font-size:11px;font-weight:bold;letter-spacing:1.5px;">ONE-TIME CODE</p>
              <p dir="ltr" style="margin:0;color:#800020;font-family:Consolas,'Courier New',monospace;font-weight:bold;line-height:1.3;{code_style}">{escape(code)}</p>
              <p style="margin:10px 0 0;font-size:13px;color:#4e1422;">Expires in {escape(expiry)}</p>
            </td></tr>
          </table>
          <p style="margin:18px 0 0;font-size:15px;line-height:1.6;">{escape(instructions)}</p>
        </td></tr>
        <tr><td style="padding:16px 24px;border-top:1px solid #e5dfd6;background-color:#fbf8f2;border-radius:0 0 15px 15px;">
          <p style="margin:0;color:#625659;font-size:13px;line-height:1.55;">{escape(security_note)}</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>""", subtype="html")
    return message
