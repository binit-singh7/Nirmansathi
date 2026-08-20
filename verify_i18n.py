import os
import sys
import django

# Setup django environment
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
django.setup()

from django.utils.translation import activate, gettext as _, get_language
from accounts.models import CustomUser, AuditLog
from locations.models import Municipality
from permits.models import PermitApplication, ApplicationDocument, PermitDecision
from marketplace.models import Order, Product
from payments.models import PaymentTransaction

print("=== VERIFYING DJANGO I18N SETUP ===")

# Test 1: English
activate('en')
print(f"Active Language: {get_language()}")
print("English Sample Translations:")
print(" - 'Apply Permit':", _("Apply Permit"))
print(" - 'Citizen Role':", str(CustomUser.Role.CITIZEN.label))
print(" - 'Metropolitan':", str(Municipality.TypeChoices.METROPOLITAN.label))
print(" - 'Approved Status':", str(PermitApplication.Status.APPROVED.label))
print(" - 'Paid Status':", str(Order.PaymentStatus.PAID.label))

assert _("Apply Permit") == "Apply Permit"
assert str(CustomUser.Role.CITIZEN.label) == "Citizen"

# Test 2: Nepali
activate('ne')
print(f"\nActive Language: {get_language()}")
print("Nepali Sample Translations:")
print(" - 'Apply Permit':", _("Apply Permit"))
print(" - 'Citizen Role':", str(CustomUser.Role.CITIZEN.label))
print(" - 'Metropolitan':", str(Municipality.TypeChoices.METROPOLITAN.label))
print(" - 'Approved Status':", str(PermitApplication.Status.APPROVED.label))
print(" - 'Paid Status':", str(Order.PaymentStatus.PAID.label))
print(" - 'Marketplace':", _("Marketplace"))
print(" - 'My Orders':", _("My Orders"))
print(" - 'Government of Nepal':", _("Government of Nepal"))

assert _("Apply Permit") == "अनुमति आवेदन", f"Expected 'अनुमति आवेदन', got '{_('Apply Permit')}'"
assert str(CustomUser.Role.CITIZEN.label) == "नागरिक", f"Expected 'नागरिक', got '{str(CustomUser.Role.CITIZEN.label)}'"
assert str(Municipality.TypeChoices.METROPOLITAN.label) == "महानगरपालिका"
assert str(PermitApplication.Status.APPROVED.label) == "स्वीकृत"
assert str(Order.PaymentStatus.PAID.label) == "भुक्तानी भयो"
assert _("Marketplace") == "निर्माण सामग्री बजार"

print("\nAll Python Translation Assertions PASSED!")
