/**
 * Permits JS Utility: Location Cascades & Document File Handling
 */

async function initLocationCascades(provinceSelectId, districtSelectId, municipalitySelectId, wardSelectId) {
    const provinceSelect = document.getElementById(provinceSelectId);
    const districtSelect = document.getElementById(districtSelectId);
    const municipalitySelect = document.getElementById(municipalitySelectId);
    const wardSelect = document.getElementById(wardSelectId);

    if (!provinceSelect || !districtSelect || !municipalitySelect || !wardSelect) return;

    // Load Provinces
    try {
        const provinces = await apiFetch('/locations/provinces/');
        provinceSelect.innerHTML = `<option value="">-- Select Province --</option>` +
            provinces.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    } catch (err) {
        showToast('Failed to load provinces', 'danger');
    }

    // Province Change -> Load Districts
    provinceSelect.addEventListener('change', async () => {
        const provId = provinceSelect.value;
        districtSelect.innerHTML = '<option value="">-- Select District --</option>';
        municipalitySelect.innerHTML = '<option value="">-- Select Municipality --</option>';
        wardSelect.innerHTML = '<option value="">-- Select Ward --</option>';
        districtSelect.disabled = true;
        municipalitySelect.disabled = true;
        wardSelect.disabled = true;

        if (!provId) return;

        try {
            const districts = await apiFetch(`/locations/districts/?province=${provId}`);
            districtSelect.innerHTML = `<option value="">-- Select District --</option>` +
                districts.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
            districtSelect.disabled = false;
        } catch (err) {
            showToast('Failed to load districts', 'danger');
        }
    });

    // District Change -> Load Municipalities
    districtSelect.addEventListener('change', async () => {
        const distId = districtSelect.value;
        municipalitySelect.innerHTML = '<option value="">-- Select Municipality --</option>';
        wardSelect.innerHTML = '<option value="">-- Select Ward --</option>';
        municipalitySelect.disabled = true;
        wardSelect.disabled = true;

        if (!distId) return;

        try {
            const municipalities = await apiFetch(`/locations/municipalities/?district=${distId}`);
            municipalitySelect.innerHTML = `<option value="">-- Select Municipality --</option>` +
                municipalities.map(m => `<option value="${m.id}">${m.name} (${m.municipality_type_display || m.municipality_type})</option>`).join('');
            municipalitySelect.disabled = false;
        } catch (err) {
            showToast('Failed to load municipalities', 'danger');
        }
    });

    // Municipality Change -> Load Wards
    municipalitySelect.addEventListener('change', async () => {
        const muniId = municipalitySelect.value;
        wardSelect.innerHTML = '<option value="">-- Select Ward --</option>';
        wardSelect.disabled = true;

        if (!muniId) return;

        try {
            const wards = await apiFetch(`/locations/wards/?municipality=${muniId}`);
            wardSelect.innerHTML = `<option value="">-- Select Ward --</option>` +
                wards.map(w => `<option value="${w.id}">Ward No. ${w.ward_number}</option>`).join('');
            wardSelect.disabled = false;
        } catch (err) {
            showToast('Failed to load wards', 'danger');
        }
    });
}
