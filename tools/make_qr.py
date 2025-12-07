# /// script
# dependencies = [
#   "qrcode",
# ]
# ///

import qrcode

qr = qrcode.QRCode(
    border=0,
    version=1,
    error_correction=qrcode.constants.ERROR_CORRECT_L,
)
# qr.add_data('https://github.com/sponsors/willmcgugan')
qr.add_data("https://tinyurl.com/52r7fd25")
qr.make(fit=True)

# Print using Unicode blocks (looks more square)
qr.print_ascii()
