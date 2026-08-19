# NirmanSathi — Software Architecture Views Specification
### 4+1 View Model — **STATUS: FINAL APPROVED (v2)** — supersedes the v1 draft after critical audit

---

## Changelog from v1 (what a critical review found and fixed)
1. Logical View now explicitly separates **client-side navigation** (cosmetic, `localStorage`-based) from **server-side RBAC enforcement** (the real security boundary, re-checked on every request) using a trust-boundary partition.
2. "Role Dashboard" is now explicitly labeled as an abstraction over 4 unrelated concrete views/templates, not a single component.
3. Domain relationships now include `UserProfile` and `ProductCategory`, previously omitted.
4. Development View's intra-app layering arrows were **factually reversed** in v1 (pointed `models→...→admin`); corrected to match the actual Python `import` direction (`urls→views→serializers/permissions→models`, `admin→models` independently).
5. Development View now notes that `locations` keeps its permission class inline in `views.py`, unlike `permits`/`marketplace`'s dedicated `permissions.py`.
6. Process View now uses separate request/response arrows (v1 conflated them into one), adds an explicit Login/Token pipeline, and surfaces that multi-request business transactions are not atomic as a whole.
7. Physical View now uses correct UML Deployment Diagram notation (undirected communication-path lines, not directional call arrows) and marks third-party CDNs `<<external>>`, outside an explicit system boundary.
8. Simulated payment now carries an explicit `<<simulated>>` stereotype directly on the diagram nodes, not only in prose.
9. Authentication description corrected: `SessionAuthentication` is configured but dormant for the actual login flow (no view calls `django.contrib.auth.login()`).

Everything else in v1 was checked against the audit's 13 criteria and confirmed accurate (inter-app dependency map, notifications correctly excluded, no SMTP anywhere, simulated-vs-real payment distinction in prose, endpoint inventory).

**Notation legend:**
```
──────>   solid arrow, filled head : synchronous runtime call / request (Logical & Scenario & Process views)
<─ ─ ─    dashed arrow, open head  : response / return value (Scenario & corrected Process views)
- - ->    dashed arrow, open head  : structural "depends on" (Development View package dependencies)
──────    plain undirected line    : physical communication path, labeled with protocol (Physical View ONLY —
                                      per UML Deployment Diagram convention, network links are not directed calls)
[Box]     component / class / process / node
┌┄┄┄┐     dashed boundary box      : trust boundary (client/untrusted vs server/trusted) or system boundary
<<...>>   UML stereotype: <<app>>, <<view>>, <<model>>, <<artifact>>, <<device>>, <<simulated>>, <<external>>, <<unconfirmed>>
```

---

## 0. Repository Reality Check *(unchanged from v1 — re-verified, still accurate)*

**Confirmed by code:** Django project `config` + apps `accounts`, `locations`, `permits`, `marketplace`, `payments`; DRF + SimpleJWT; `CustomUser.role` RBAC; hybrid MPA (server-rendered templates + vanilla JS calling `/api/v1/`); JWT in `localStorage`; simulated payment fabricated entirely in-process; SQLite (not PostgreSQL) in the authoritative `settings.py`; local filesystem media storage; Django Admin registered and functional.

**Documented as intent but not implemented — never draw as real:** PostgreSQL, Render/Railway deployment, real eSewa/Khalti/bank gateway, architect/contractor/equipment-rental marketplace, GIS, AI blueprint validation, digital signatures, SMS/email notifications, a working admin user-management API (only Django's built-in `/admin/` is real; `admin_dashboard.html`'s user table and `audit_logs.html` are both hardcoded JS demo arrays, not API-backed).

**Never mentioned anywhere — must not appear:** Docker, Kubernetes, microservices, Redis, Celery/task queues, message brokers, load balancers, managed cloud services, WebSockets/Channels, SMTP/email server.

---

## 1. Logical View

**Purpose:** functional decomposition and business logic, per your lecturer's requirement.
**Notation:** UML Package Diagram (subsystems) + UML Class relationships (domain model) + Activity-style flow (the 3 required logic chains) + an explicit trust-boundary partition. These are three complementary diagrams composing one view, not one blended diagram.

### 1.1 Top-level component map
| Component | Maps to (evidence) |
|---|---|
| Presentation Layer (client, untrusted) | `templates/*.html` + `base.js`, `cart.js`, `permits.js` |
| Authentication & RBAC (server, trusted) | `accounts.CustomUser(role)`, SimpleJWT views, per-app DRF permission classes |
| Role-Scoped Views *(abstraction — see §1.2 note)* | 4 unrelated dashboard views/templates |
| Location Reference Data | `locations`: `Province → District → Municipality → Ward` |
| E-Governance (Permits) | `permits`: `PermitApplication`, `ApplicationDocument`, `PermitDecision` |
| Marketplace | `marketplace`: `ProductCategory`, `Product`, `ShoppingCart`, `CartItem`, `Order`, `OrderItem` |
| Payments *(simulated)* | `payments`: `PaymentTransaction`, `SimulateEsewaPaymentView` |

### 1.2 Master flow — corrected, with explicit trust boundary
```
┌┄┄┄┄┄┄┄┄┄┄ CLIENT (untrusted) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┊ [Login form] ──POST login/──> obtains JWT + role            ┊
┊      |                                                       ┊
┊      v                                                       ┊
┊ [Client-side role-based redirect / nav] (base.js, reads      ┊
┊  role from localStorage — UX convenience, NOT a security     ┊
┊  boundary; can be bypassed by editing localStorage)          ┊
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
                        | every subsequent API call, independently re-authorized
                        v
┌┄┄┄┄┄┄┄┄┄┄ SERVER (trusted — the real enforcement point) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┊ [DRF permission class per endpoint: IsPermitParticipant /                ┊
┊  IsSupplierOrReadOnly / IsAdminOrReadOnly / IsAuthenticated]             ┊
┊         |                                    |                          ┊
┊         v                                    v                          ┊
┊  [E-Governance module]              [Marketplace module]                ┊
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
```
`REST_FRAMEWORK.DEFAULT_PERMISSION_CLASSES = (IsAuthenticatedOrReadOnly,)` is the global fallback, but every ViewSet explicitly overrides it — the default is configured, never relied upon in practice.

**Note on "Role-Scoped Views":** this is an abstraction over 4 unrelated concrete Django views/templates (`CitizenDashboardView`, `OfficerDashboardView`, `SupplierDashboardView`, `AdminDashboardView`) — there is no shared base class or dashboard framework in the code. Do not present it as one polymorphic component.

### 1.3 Permit logic chain (E-Governance) — unchanged, verified correct
```
[Permit Application] ──> [Document Upload / Validation] ──> [Officer Review] ──> [Approval / Rejection] ──> [Status Tracking]
```
| Step | Component (exact) |
|---|---|
| Permit Application | `PermitApplicationViewSet.create()` → `PermitApplication` (`status=PENDING`, auto `reference_number`) |
| Document Upload/Validation | `ApplicationDocumentViewSet.create()` → `ApplicationDocument`. **Validation caveat:** `PermitApplication.clean()` (cost/area > 0) is never invoked through the DRF serializer path (no `full_clean()` call) — enforcement today is only HTML5 `min` attributes + DB field types. File-type restriction is only the browser's `accept=".pdf,.png,.jpg,.jpeg"` hint — no server-side `FileExtensionValidator`. |
| Officer Review | `PermitApplicationViewSet.review()` — scoping caveat: `ApplicationDocumentViewSet`'s own queryset (`application__applicant=user`) would return empty for an officer querying it directly; officers only see documents via the **nested** `documents[]` field inside `PermitApplicationViewSet`'s response, which *is* correctly scoped. |
| Approval/Rejection | `review()`, inside `transaction.atomic()`: creates `PermitDecision`, updates `PermitApplication.status`/`.remarks` |
| Status Tracking | `PermitApplicationViewSet.get_queryset()` scoped by `IsPermitParticipant` |

### 1.4 Marketplace logic chain — unchanged, verified correct
```
[Product Catalogue] ──> [Cart] ──> [Checkout] ──> [<<simulated>> Simulated Payment] ──> [Order Confirmation]
```
`ProductViewSet`/`ProductCategoryViewSet` → `ShoppingCartViewSet.add_item()`/`.remove_item()` → `ShoppingCartViewSet.checkout()` (atomic: creates `Order` `PENDING`/`UNPAID`, `OrderItem`s, decrements stock, clears cart) → see §1.5 → `order_detail.html`.

### 1.5 Payment logic chain — explicit simulated stereotype, verified correct
```
[Checkout] ──> [Payment Request] ──> [<<simulated>> Simulated Payment] ──┬──> [Success] ──> [Payment Status=PAID] ──> [Order=CONFIRMED]
                                                                          └──> [Failure] ──> [Payment Status stays UNPAID] ──> [Order stays PENDING]
```
`SimulateEsewaPaymentView.post()` builds a fake `gateway_response` dict **entirely in-process** — zero outbound network calls to any real gateway. The success/failure branch is controlled by a `simulate_failure` boolean the client itself supplies (a testing toggle), not a real payment outcome. Do not draw a gateway boundary, webhook, or callback URL — none exist.

### 1.6 Notifications — confirmed absent, correctly excluded
`showToast()` is synchronous client-side UI feedback tied to the immediate `fetch()` response — no persistence, no cross-user delivery, no backend service. No `EMAIL_BACKEND`, no `django.core.mail`, no Celery, no signal-driven messaging anywhere. **`Notification Service → SMTP/TLS → SMTP Mail Server` correctly does not appear anywhere in this specification** — audit-confirmed clean.

### 1.7 Domain relationships (corrected — now complete)
```
CustomUser ──1───1── UserProfile                     [added — was missing in v1]
CustomUser ──1───*── PermitApplication (applicant)
CustomUser ──1───*── PermitDecision (officer)
CustomUser ──1───*── Product (supplier)
CustomUser ──1───*── Order (buyer)
CustomUser ──1───*── PaymentTransaction (user)
Municipality ──1───*── PermitApplication         [on_delete=PROTECT]
Ward ──1───*── PermitApplication                 [on_delete=PROTECT]
PermitApplication ──1───*── ApplicationDocument
PermitApplication ──1───*── PermitDecision
ProductCategory ──1───*── Product                [added — was missing in v1; on_delete=PROTECT]
Product ──1───*── CartItem, OrderItem            [OrderItem.product uses on_delete=SET_NULL — order history survives product deletion]
ShoppingCart ──1───*── CartItem
Order ──1───*── OrderItem
Order ──1───*── PaymentTransaction
```

### 1.8 What must NOT appear
Notification/messaging service; architect/contractor/equipment-rental modules; real payment gateway/webhook; admin "user management" as a live API feature; audit-logging subsystem; GIS/AI/digital-signature modules.

---

## 2. Process View

**Purpose:** runtime processes, complete request lifecycles, concurrency.
**Notation:** UML Activity Diagram (single-lane, sequential — corrected from the imprecise "swimlane" label in v1) for pipelines; distinct request/response arrows throughout (corrected from v1's conflated single arrow).

### 2.1 Runtime processes (actual)
```
[Browser Process: JS engine]
        |  HTTP request (solid, filled head)
        v
[Django Application Process: single WSGI process — serves BOTH
 template pages AND the /api/v1/ REST API]
        |  ORM query (in-process, synchronous)
        v
[SQLite: embedded file, same OS process — NOT a separate DB server]
        |
        ^  HTTP response (dashed, open head) — SEPARATE arrow, corrected from v1
[Browser Process]
```

### 2.2 Pipeline A — server-rendered page load
```
Browser ──GET /permits/apply/──> URL Router ──> Middleware chain (§2.4) ──> Page View
   (views.PermitCreateView, etc. — location unconfirmed, see §3.1 note)
   ──> renders templates/permits/application_create.html
Browser <── HTML response ── (separate return arrow)
```

### 2.3 Pipeline B — AJAX / REST call, with decision branch
```
Browser JS (apiFetch, Authorization: Bearer <JWT>) ──fetch()──> URL Router
   ──> Middleware chain (§2.4) ──> DRF ViewSet.dispatch()
        ──> DRF Authentication (JWTAuthentication; SessionAuthentication configured
             but dormant — no view calls django.contrib.auth.login(), so it only
             ever applies to a separate /admin/-authenticated session, if any)
        ──> DRF Permission check
        ──> ViewSet method ──> Serializer ──> ORM ──> SQLite
        ──[checkout only]──> decision: stock sufficient?
              ── yes ──> atomic: create Order+OrderItems, decrement stock, clear cart
              ── no  ──> raises ValueError (500, NOT a clean 400 — atomic() still
                          rolls back correctly, but the HTTP response is an
                          unhandled-exception response)
Browser <── JSON response ── (separate return arrow)
Browser JS parses JSON ──> updates DOM / redirect / showToast()
```

### 2.4 Middleware order (exact, from `settings.py`)
```
1. corsheaders.middleware.CorsMiddleware
2. django.middleware.security.SecurityMiddleware
3. django.contrib.sessions.middleware.SessionMiddleware
4. django.middleware.common.CommonMiddleware
5. django.middleware.csrf.CsrfViewMiddleware
6. django.contrib.auth.middleware.AuthenticationMiddleware
7. django.contrib.messages.middleware.MessageMiddleware
8. django.middleware.clickjacking.XFrameOptionsMiddleware
```
DRF authentication/permission checks run inside view dispatch, **after** this chain — not as a Django middleware stage.

### 2.5 Pipeline C — Authentication (added; was missing in v1)
```
Browser ──POST login/ {username,password}──> TokenObtainPairView ──validates hashed password──> DB
Browser <── {access, refresh JWT} ──
Browser ──GET me/ (Bearer <JWT>)──> CurrentUserView ──> DB
Browser <── {role, municipality, ...} ──
Browser: client-side redirect by role (cosmetic — see §1.2 trust boundary)
```
Login is genuinely **two sequential HTTP requests**, not one — worth stating explicitly since it's arguably the most fundamental runtime process in the system.

### 2.6 Cross-request transaction integrity (added; was missing in v1)
`transaction.atomic()` guards each *individual* request, not a multi-request business transaction as a whole:
- If document upload fails/is abandoned after a permit application is successfully created, the `PermitApplication` persists with zero documents and nothing flags or rolls it back.
- If a citizen completes checkout (creating an `Order` as `PENDING`/`UNPAID`) but never completes the payment-simulation step, the `Order` remains stuck indefinitely — no timeout, cron job, or cleanup process exists (consistent with §0: no task queue in this system).

### 2.7 What must NOT appear
Multiple app-server replicas; a separate DB server process (true only once PostgreSQL is actually wired in); background workers/queues; caching processes; WebSocket channels.

---

## 3. Development View

**Purpose:** actual code/package structure.
**Notation:** UML Component/Package Diagram; dependency arrows sourced directly from `import` statements and migration `dependencies=[...]` declarations — not inferred.

### 3.1 Actual repository tree
```
NirmanSathi/
├── README.md, .gitignore
├── requirements.txt              (referenced in README tree; contents not provided — cannot confirm installed packages)
├── designs/, docs/{feasibility,proposal,srs}/, scripts/  (docs confirmed; designs/scripts are .gitkeep-only)
└── src/
    ├── manage.py
    ├── views.py                  <<unconfirmed>> — config/urls.py does `import views`; file itself not
    │                                 supplied. Inferred location only. Mark with <<unconfirmed>> in any
    │                                 diagram, don't present it as verified fact.
    ├── config/        settings.py, urls.py, asgi.py, wsgi.py
    ├── accounts/       models.py, serializers.py, views.py, urls.py, admin.py, apps.py, tests.py, migrations/
    ├── locations/      models.py, serializers.py, views.py <<permission class defined inline here>>, urls.py, admin.py, apps.py, tests.py, migrations/
    ├── permits/        models.py, serializers.py, views.py, permissions.py, urls.py, admin.py, apps.py, tests.py, migrations/
    ├── marketplace/    models.py, serializers.py, views.py, permissions.py, urls.py, admin.py, apps.py, tests.py, migrations/
    ├── payments/       models.py, serializers.py, views.py, urls.py, admin.py, apps.py, tests.py, migrations/  (no permissions.py)
    ├── templates/      base.html, home.html, accounts/, dashboard/, permits/, marketplace/
    └── static/         css/base.css, js/{base.js, cart.js, permits.js}
```
*Gitignored at runtime, not in the tree: `db.sqlite3`, `media/`, `staticfiles/`, `venv/`.*

### 3.2 Per-app internal layering — **corrected direction** (was reversed in v1)
```
urls.py  - -depends on-> views.py  - -depends on-> serializers.py  - -depends on-> models.py
                              |
                              └ - -depends on-> permissions.py    (leaf; permits & marketplace only —
                                                                    locations has this inline in views.py instead)
admin.py - - - - - - - - - - - - - - - - - - - - - -depends on-> models.py    (independent path, no
                                                                    dependency on views/serializers)
```
Verified against literal `import` statements (e.g. `permits/serializers.py: from .models import ...`; `permits/views.py: from .models import ...`, `from .serializers import ...`, `from .permissions import IsPermitParticipant`; `permits/urls.py: from .views import ...`; `permits/admin.py: from .models import ...`). This is the reverse of what v1 drew.

### 3.3 Inter-app dependency map — verified correct in v1, unchanged
```
locations         (no dependency on other project apps)
accounts    - - -> locations        (CustomUser.municipality FK)
permits     - - -> accounts         (applicant/officer FK)
permits     - - -> locations        (municipality/ward FK)
marketplace - - -> accounts         (supplier/buyer FK)
payments    - - -> marketplace      (order FK)
payments    - - -> accounts         (user FK)
config      - - -> accounts, locations, permits, marketplace, payments
```
**Why this doesn't duplicate the Logical View's component map (§1.1):** §1.1 groups the same 5 apps by *business capability* and shows *workflow* (activity-style, temporal sequence). §3.3 groups them by *code module* and shows *structural import/FK dependency* (static, "who imports/references whom"). Same 5 nodes, genuinely different question and different arrow semantics — not a redundant diagram.

### 3.4 Confirmed REST endpoint inventory — unchanged, verified correct
```
/api/v1/accounts/    register/, login/, token/refresh/, me/, profile/
/api/v1/locations/   provinces/, districts/, municipalities/, wards/   (full CRUD, write=staff only)
/api/v1/permits/     applications/, applications/<id>/review/, documents/
/api/v1/marketplace/ categories/(read-only), products/, cart/, cart/add-item/,
                      cart/remove-item/<id>/, cart/checkout/, orders/, orders/<id>/update-status/
/api/v1/payments/    esewa/simulate/, transactions/
/admin/              Django's built-in admin (separate from the custom dashboards)
```

### 3.5 What must NOT appear
Separate frontend repo/build pipeline (Bootstrap/Fonts loaded via `<link>` CDN tags, no bundler evident); multiple deployable codebases; a populated automated test suite (every `tests.py` is the unmodified stub); CI/CD pipeline (none provided).

---

## 4. Physical View

**Purpose:** actual deployment topology.
**Notation:** UML Deployment Diagram — nodes as `<<device>>`/`<<execution environment>>`, artifacts inside nodes, **plain undirected communication-path lines** labeled with protocol (corrected from v1's incorrect directional arrows), explicit system boundary, `<<external>>` stereotype for third-party nodes.

### 4.1 Current, actual topology
```
┌┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ SYSTEM BOUNDARY: NirmanSathi deployment (current) ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┐
┊ <<device>> Developer / Host Machine                                                       ┊
┊  ┌─────────────────────────────────────────────────────────────────────┐                 ┊
┊  │ <<execution environment>> Django Dev Server (manage.py runserver)     │                 ┊
┊  │   <<artifact>> config, accounts, locations, permits, marketplace,     │                 ┊
┊  │                 payments (Django apps)                                │                 ┊
┊  │   <<artifact>> templates/ (server-rendered)                           │                 ┊
┊  │   <<artifact>> /admin/ (Django built-in admin, same process)          │                 ┊
┊  │                                                                       │                 ┊
┊  │   <<artifact>> db.sqlite3 (embedded file, same process — NOT a        │                 ┊
┊  │                 separate DB server)                                   │                 ┊
┊  │   <<artifact>> media/ (uploaded blueprints, Lalpurja, images —        │                 ┊
┊  │                 local filesystem)                                     │                 ┊
┊  │   <<artifact>> static/ (served by Django's static() helper, DEBUG=True)│                 ┊
┊  └─────────────────────────────────────────────────────────────────────┘                 ┊
└┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┘
       │
       │ HTTP (no TLS/certificate configured — DEBUG=True, ALLOWED_HOSTS=['*'],
       │        CORS_ALLOW_ALL_ORIGINS=True: a dev configuration, not production-hardened)
       │
<<device>> Client Browser
       │
       │ HTTPS  (separate, unrelated to the above — browser fetches these directly)
       ├──── <<external>> jsdelivr CDN (Bootstrap CSS/JS, Bootstrap Icons)
       └──── <<external>> Google Fonts CDN (Inter font)
```

### 4.2 Documented target — not yet implemented (annotation only, never a solid node)
PostgreSQL as a separate DB node; deployment on Render/Railway (named "Deployment (Future)" in the Proposal, no config files exist). `requirements.txt` contents were never supplied, so whether `psycopg2`/`gunicorn`/`whitenoise` are even installed cannot be confirmed — verify before claiming any production-readiness.

### 4.3 What must NOT appear
Docker/Kubernetes; load balancers; multiple app-server replicas; Redis/cache nodes; message-broker nodes; AWS/Azure/GCP managed services; a CDN you operate; a TLS-terminating reverse proxy; SQLite drawn as a separate "server" node.

---

## 5. Scenario / Sequence View

**Notation:** UML Sequence Diagram — solid+filled = request, dashed+open = response, activation bars on the receiving lifeline. `<<simulated>>` stereotype applied directly on the payment node (corrected from v1, where it was prose-only).

### 5.1 Scenario A — Permit Application → Officer Review → Decision → Status Tracking
*(unchanged from v1 — already used correct distinct request/response arrows; audit found no error here)*
```
Citizen(Browser)          PermitApplicationViewSet     ApplicationDocumentViewSet     DB          Officer(Browser)
     |  POST applications/ {building info}      |                                      |               |
     |───────────────────────────────────────> |                                      |               |
     |                                           |── perform_create(applicant=user) ─>|               |
     |  <── 201 {id, reference_number} ───────── |                                      |               |
     |  POST documents/ (multipart: BLUEPRINT, then LALPURJA — two separate requests,   |               |
     |     no atomicity across them — see §2.6) ─────────────────────────────────────> |               |
     |  <── 201 (each) ──────────────────────────────────────────────────────────────  |               |
     |                                                          GET applications/ (officer queue, municipality-scoped)
     |                                                                                                    |<──────────────|
     |                                                                                                    |── list ──────>|
     |                                                          POST applications/<id>/review/ {decision, remarks}
     |                                                                                                    |<──────────────|
     |                                                          [atomic: create PermitDecision, update status/remarks]
     |                                                                                                    |── 200 ───────>|
     |  GET applications/<id>/ (status tracking + officer remarks + decision history)                                    |
     |──────────────────────────────────────────────────────────────>|                                                  |
     |  <── 200 {status_display, remarks, decisions[]} ────────────── |                                                  |
```

### 5.2 Scenario B — Browse → Cart → Checkout → Simulated Payment → Order Confirmation
```
Citizen(Browser)   ProductViewSet   ShoppingCartViewSet   <<simulated>> SimulateEsewaPaymentView   DB
     | GET products/, categories/                                                                   |
     |─────────────>|  <── list ──|                                                                  |
     | POST cart/add-item/ {product_id, qty}                                                        |
     |───────────────────────────>|── validate stock, get_or_create CartItem ────────────────────────>|
     | <── 200 cart ──────────────|                                                                    |
     | POST cart/checkout/ {shipping_address, contact_phone}                                          |
     |───────────────────────────>|── decision: stock sufficient? (§2.3) ── atomic: Order(PENDING/UNPAID),
     |                             |   OrderItem(s), decrement stock, clear cart ─────────────────────>|
     | <── 201 {order} ───────────|                                                                    |
     | POST esewa/simulate/ {order_id, simulate_failure}     (<<simulated>> — no external gateway call)|
     |───────────────────────────────────────────────────────────────>|                                |
     |                                                                  |── build fake gateway_response  |
     |                                                                  |   (in-process only) ──atomic: |
     |                                                                  |   create PaymentTransaction;   |
     |                                                                  |   IF success: Order.payment_status=PAID,
     |                                                                  |   Order.status=CONFIRMED ─────>|
     | <── 200/400 {transaction} ───────────────────────────────────────|                                |
     | GET orders/<id>/ (order confirmation)                                                            |
     |──────────────────────────────────────────────────────────────────────────────────────────────────>|
     | <── {payment_status, status, items[]} ───────────────────────────────────────────────────────────  |
```
**Known bug, flag before any live demo:** `supplier_dashboard.html` PATCHes `orders/<id>/` to update fulfilment status, but `OrderViewSet` is `ReadOnlyModelViewSet` (only `list`/`retrieve` + the custom `POST .../update-status/` action exist) — that `PATCH` returns `405`.

### 5.3 Cross-check against the other four views
Both scenarios use only endpoints listed in §3.4; both match Pipeline B (§2.3) exactly, request by request; both fit inside the single-node Physical View (§4.1) with no additional infrastructure required; both trace directly to the Logical View's three required chains (§1.3–1.5) with no invented steps.

---

## 6. Verified Inconsistencies & Recommendations (carried forward + one new item from the audit)
1. DB engine: SQLite (actual) vs PostgreSQL (documented) — resolve or present honestly.
2. `OrderViewSet` PATCH mismatch — fix before demoing supplier order fulfilment.
3. Admin user management and audit log page are both hardcoded JS demo data, not real API features.
4. `views.py` location is inferred, not confirmed — verify the actual path.
5. `requirements.txt` contents unknown — confirm production-package status before claiming deployability.
6. Checkout's stock-insufficiency path raises an unhandled `ValueError` (500) instead of a clean 400.
7. **(New)** `ApplicationDocumentViewSet`'s standalone queryset is not scoped for officers — only works today because the UI never calls it directly, relying instead on the nested `documents[]` field on `PermitApplicationViewSet`.

---

## 7. Recommended Slide-by-Slide Presentation Structure
1. Title slide.
2. System context (current implementation scope only, per Proposal §8).
3. Technology stack (actual) — flag PostgreSQL/Render as planned, not current.
4. 4+1 View Model overview.
5. Logical View — master flow with trust boundary (§1.2).
6. Logical View — Permit logic chain (§1.3).
7. Logical View — Marketplace logic chain (§1.4).
8. Logical View — Payment logic chain, `<<simulated>>` clearly marked (§1.5).
9. Logical View — what's deliberately excluded (notifications, real gateway) and why.
10. Process View — runtime processes + Login pipeline (§2.1, §2.5).
11. Process View — REST pipeline, middleware order, cross-request integrity caveat (§2.3, §2.6).
12. Development View — repository structure (§3.1).
13. Development View — corrected dependency diagrams, intra- and inter-app (§3.2, §3.3).
14. Physical View — current topology with system boundary (§4.1).
15. Physical View — documented target vs. actual (honesty slide) (§4.2).
16. Scenario View — Permit sequence (§5.1).
17. Scenario View — Marketplace/Payment sequence, known bug flagged (§5.2).
18. Audit trail slide — "how this architecture was validated" (§6) — strong for viva credibility.
19. Future scope (clearly labeled as future).
20. Q&A.

---

## 8. Sign-off against the 13 audit criteria
| # | Criterion | Status |
|---|---|---|
| 1 | Logical View = real business logic | ✅ trust boundary added, domain gaps closed |
| 2 | Process View = complete runtime workflow | ✅ Login pipeline + cross-request integrity added |
| 3 | Development View = actual structure | ✅ intra-app arrows corrected |
| 4 | Physical View = actual deployment | ✅ correct Deployment Diagram notation, system boundary |
| 5 | UML notation appropriate | ✅ activity/deployment/sequence notation now applied correctly per view |
| 6 | Arrows logically correct | ✅ all conflated/reversed arrows fixed |
| 7 | No invented components | ✅ confirmed; abstractions now explicitly labeled as such |
| 8 | No missing components | ✅ UserProfile, ProductCategory, Login pipeline, atomicity gaps added |
| 9 | Simulated vs real payment | ✅ `<<simulated>>` stereotype now on every diagram, not just prose |
| 10 | Notification protocol shown only if implemented | ✅ N/A, correctly absent |
| 11 | SMTP/TLS only if implemented | ✅ confirmed absent, zero email code anywhere |
| 12 | Four views sufficiently distinct | ✅ Logical-vs-Development overlap explicitly justified (§3.3) |
| 13 | Viva-defensible | ✅ every remaining component traces to a specific file/class/import statement |

*This is the final, audited version. Every component, arrow, and workflow is traceable to a specific file, class, method, or import statement in the material you provided.*
