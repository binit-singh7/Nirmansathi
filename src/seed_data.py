import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from locations.models import Province, District, Municipality, Ward
from marketplace.models import ProductCategory, Product
from accounts.models import UserProfile

User = get_user_model()

def seed_db():
    print("[+] Seeding NirmanSathi database...")

    # 1. Seed Locations
    p3, _ = Province.objects.get_or_create(code=3, defaults={'name': 'Bagmati Province'})
    ktm_dist, _ = District.objects.get_or_create(name='Kathmandu', defaults={'province': p3})
    ktm_muni, _ = Municipality.objects.get_or_create(
        name='Kathmandu Metropolitan City',
        defaults={'district': ktm_dist, 'type': Municipality.TypeChoices.METROPOLITAN}
    )
    lalitpur_dist, _ = District.objects.get_or_create(name='Lalitpur', defaults={'province': p3})
    lalitpur_muni, _ = Municipality.objects.get_or_create(
        name='Lalitpur Metropolitan City',
        defaults={'district': lalitpur_dist, 'type': Municipality.TypeChoices.METROPOLITAN}
    )

    w10, _ = Ward.objects.get_or_create(municipality=ktm_muni, ward_number=10)
    w3, _ = Ward.objects.get_or_create(municipality=ktm_muni, ward_number=3)

    print("  - Created Provinces, Districts, Municipalities, and Wards.")

    # 2. Seed Users & Admin
    admin_user, admin_created = User.objects.get_or_create(
        username='admin',
        defaults={
            'email': 'admin@nirmansathi.gov.np',
            'role': User.Role.ADMIN,
            'is_staff': True,
            'is_superuser': True,
            'municipality': ktm_muni
        }
    )
    if admin_created:
        admin_user.set_password('Admin@12345')
        admin_user.save()
        UserProfile.objects.get_or_create(user=admin_user, full_name='System Administrator')
        print("  - Created Superuser: admin (password: Admin@12345)")

    officer_user, officer_created = User.objects.get_or_create(
        username='officer_ktm',
        defaults={
            'email': 'officer@ktm.gov.np',
            'role': User.Role.MUNICIPALITY_OFFICER,
            'phone_number': '9801234567',
            'municipality': ktm_muni
        }
    )
    if officer_created:
        officer_user.set_password('Officer@12345')
        officer_user.save()
        UserProfile.objects.get_or_create(user=officer_user, full_name='Ramesh Sharma (KTM Officer)')
        print("  - Created Municipality Officer: officer_ktm (password: Officer@12345)")

    citizen_user, citizen_created = User.objects.get_or_create(
        username='citizen_ram',
        defaults={
            'email': 'ram@gmail.com',
            'role': User.Role.CITIZEN,
            'phone_number': '9841112233',
            'municipality': ktm_muni
        }
    )
    if citizen_created:
        citizen_user.set_password('Citizen@12345')
        citizen_user.save()
        UserProfile.objects.get_or_create(user=citizen_user, full_name='Ram Bahadur Thapa', citizenship_number='27-01-78-01234')
        print("  - Created Citizen user: citizen_ram (password: Citizen@12345)")

    supplier_user, supplier_created = User.objects.get_or_create(
        username='supplier_prakash',
        defaults={
            'email': 'prakash@buildmaterials.np',
            'role': User.Role.MATERIAL_SUPPLIER,
            'phone_number': '9851098765'
        }
    )
    if supplier_created:
        supplier_user.set_password('Supplier@12345')
        supplier_user.save()
        UserProfile.objects.get_or_create(
            user=supplier_user,
            full_name='Prakash Shrestha',
            company_name='Himalaya Construction Suppliers Pvt Ltd',
            company_pan_vat='601234567'
        )
        print("  - Created Material Supplier: supplier_prakash (password: Supplier@12345)")

    # 3. Seed Marketplace Categories & Products
    cement_cat, _ = ProductCategory.objects.get_or_create(
        slug='cement',
        defaults={'name': 'Cement', 'description': 'OPC & PPC High Grade Cement'}
    )
    steel_cat, _ = ProductCategory.objects.get_or_create(
        slug='steel-rebar',
        defaults={'name': 'Steel & Rebar', 'description': 'Fe500D TMT Steel Rods'}
    )
    aggregates_cat, _ = ProductCategory.objects.get_or_create(
        slug='sand-aggregates',
        defaults={'name': 'Sand & Aggregates', 'description': 'Washed River Sand and Crushed Stone Aggregates'}
    )

    Product.objects.get_or_create(
        supplier=supplier_user,
        name='Shivam OPC Cement (50kg)',
        defaults={
            'category': cement_cat,
            'price': 750.00,
            'unit': 'Bag',
            'available_stock': 500,
            'description': 'High strength Grade 43 OPC Cement suitable for structural RCC work.'
        }
    )

    Product.objects.get_or_create(
        supplier=supplier_user,
        name='Panchakanya TMT Fe500D Rebar (12mm)',
        defaults={
            'category': steel_cat,
            'price': 105.00,
            'unit': 'Kg',
            'available_stock': 2500,
            'description': 'Earthquake-resistant TMT steel rebars certified to Nepal Standards.'
        }
    )

    print("  - Seeded Product Categories and Initial Material Products.")

    # 4. Seed Initial Audit Logs
    from accounts.models import AuditLog
    if not AuditLog.objects.exists():
        AuditLog.objects.create(category=AuditLog.Category.AUTH, actor=admin_user, actor_username='admin', action="System Initialization & Superuser Creation", ip_address='127.0.0.1', status=AuditLog.Status.SUCCESS)
        AuditLog.objects.create(category=AuditLog.Category.AUTH, actor=officer_user, actor_username='officer_ktm', action="Officer Account Provisioned for Kathmandu Metropolitan City", ip_address='127.0.0.1', status=AuditLog.Status.SUCCESS)
        AuditLog.objects.create(category=AuditLog.Category.PERMIT, actor=citizen_user, actor_username='citizen_ram', action="Submitted Residential Building Permit Application (Ref: KTM-PERMIT-2026-001)", ip_address='127.0.0.1', status=AuditLog.Status.SUCCESS)
        AuditLog.objects.create(category=AuditLog.Category.MARKETPLACE, actor=supplier_user, actor_username='supplier_prakash', action="Published Material Product 'Shivam OPC Cement (50kg)' to Marketplace", ip_address='127.0.0.1', status=AuditLog.Status.SUCCESS)
        print("  - Seeded initial Audit Logs.")

    print("[+] Seeding complete!")


if __name__ == '__main__':
    seed_db()
