import os

import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "moneta.settings")
django.setup()

from planning.tasks import notify_goal_progress
from wallets.tasks import update_and_notify_closed_credit_card_bills

try:
    print("Running update_and_notify_closed_credit_card_bills...")
    update_and_notify_closed_credit_card_bills()
    print("Done.")

    print("Running notify_goal_progress...")
    notify_goal_progress()
    print("Done.")
except Exception:
    import traceback
    traceback.print_exc()

