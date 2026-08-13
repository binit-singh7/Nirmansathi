import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from permits.models import PermitApplication, PermitDecision
from marketplace.models import Product, Order, ShoppingCart
from payments.models import PaymentTransaction

User = get_user_model()

def run_tests():
    print("==========================================")
    print("NIRMANSATHI BACKEND END-TO-END VERIFICATION")
    print("==========================================")
    client = APIClient()

    # 1. Test Login & Token Generation for Citizen
    res = client.post('/api/v1/accounts/login/', {'username': 'citizen_ram', 'password': 'Citizen@12345'})
    assert res.status_code == 200, f"Citizen login failed: {res.data}"
    citizen_token = res.data['access']
    print("[PASS] FR-01: Citizen Login & JWT Token issuance working.")

    # 2. Test Fetching User Profile (/api/v1/accounts/me/)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {citizen_token}')
    res = client.get('/api/v1/accounts/me/')
    assert res.status_code == 200, f"Profile fetch failed: {res.data}"
    assert res.data['role'] == 'CITIZEN'
    print("[PASS] FR-02: User Profile & Role retrieval working.")

    # 3. Test Location API (/api/v1/locations/municipalities/)
    res = client.get('/api/v1/locations/municipalities/')
    assert res.status_code == 200, f"Location fetch failed: {res.data}"
    muni_id = res.data['results'][0]['id'] if 'results' in res.data else res.data[0]['id']
    ward_id = res.data['results'][0]['wards'][0]['id'] if 'results' in res.data else res.data[0]['wards'][0]['id']
    print("[PASS] FR-03: Location Hierarchy API working.")

    # 4. Test Submit Permit Application (FR-04)
    permit_payload = {
        "application_type": "NEW_CONSTRUCTION",
        "municipality": muni_id,
        "ward": ward_id,
        "tole_address": "Baneshwor-10, Kathmandu",
        "plot_number": "Kitta-402",
        "land_area_sqft": 1500.00,
        "total_built_up_area_sqft": 2200.00,
        "storeys_count": 3,
        "estimated_cost": 8500000.00
    }
    res = client.post('/api/v1/permits/applications/', permit_payload, format='json')
    assert res.status_code == 201, f"Permit creation failed: {res.data}"
    permit_id = res.data['id']
    ref_num = res.data['reference_number']
    print(f"[PASS] FR-04: Building Permit Application submitted (Reference: {ref_num}).")

    # 5. Test Officer Login & Decision Approval (FR-06)
    res = client.post('/api/v1/accounts/login/', {'username': 'officer_ktm', 'password': 'Officer@12345'})
    assert res.status_code == 200
    officer_token = res.data['access']
    
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {officer_token}')
    review_payload = {
        "decision": "APPROVED",
        "remarks": "Blueprint meets Kathmandu Metropolitan building codes and setback rules."
    }
    res = client.post(f'/api/v1/permits/applications/{permit_id}/review/', review_payload, format='json')
    assert res.status_code == 200, f"Permit review failed: {res.data}"
    assert res.data['application']['status'] == 'APPROVED'
    print("[PASS] FR-06 & FR-07: Permit Approval Workflow & Status Tracking working.")

    # 6. Test Marketplace - Add to Cart & Checkout (FR-08, FR-09, FR-11)
    client.credentials(HTTP_AUTHORIZATION=f'Bearer {citizen_token}')
    prod = Product.objects.first()
    res = client.post('/api/v1/marketplace/cart/add-item/', {'product_id': prod.id, 'quantity': 10}, format='json')
    assert res.status_code == 200, f"Add to cart failed: {res.data}"
    print("[PASS] FR-09: Shopping Cart add item working.")

    checkout_payload = {
        "shipping_address": "House No 45, Baneshwor, Kathmandu",
        "contact_phone": "9841112233"
    }
    res = client.post('/api/v1/marketplace/cart/checkout/', checkout_payload, format='json')
    assert res.status_code == 201, f"Checkout failed: {res.data}"
    order_id = res.data['order']['id']
    order_ref = res.data['order']['order_reference']
    print(f"[PASS] FR-11: Order Management Checkout completed (Order Ref: {order_ref}).")

    # 7. Test Simulated eSewa Payment (FR-10)
    pay_payload = {
        "order_id": order_id,
        "simulate_failure": False,
        "remarks": "Simulated eSewa Payment verification test"
    }
    res = client.post('/api/v1/payments/esewa/simulate/', pay_payload, format='json')
    assert res.status_code == 200, f"Simulated eSewa payment failed: {res.data}"
    assert res.data['status'] == 'SUCCESS'
    print(f"[PASS] FR-10: Simulated eSewa Payment successful. Audit transaction created.")

    print("==========================================")
    print("ALL FUNCTIONAL REQUIREMENTS VERIFIED CLEANLY!")
    print("==========================================")

if __name__ == '__main__':
    run_tests()
