/**
 * Permits JS Utility: Location Cascades & Document File Handling
 */

async function initLocationCascades(provinceSelectId, districtSelectId, municipalitySelectId, wardSelectId) {
    const provinceSelect = document.getElementById(provinceSelectId);
    const districtSelect = document.getElementById(districtSelectId);
    const municipalitySelect = document.getElementById(municipalitySelectId);
    const wardSelect = document.getElementById(wardSelectId);

    if (!provinceSelect || !districtSelect || !municipalitySelect || !wardSelect) return;

    const resetSelect = (select, placeholder) => {
        select.innerHTML = `<option value="">${placeholder}</option>`;
        select.disabled = true;
    };

    const setOptions = (select, items, formatter, placeholder) => {
        const options = items.map(formatter).join('');
        select.innerHTML = `<option value="">${placeholder}</option>${options}`;
        select.disabled = items.length === 0;
    };

    try {
        const provinces = await apiFetch('/locations/provinces/');
        provinceSelect.innerHTML = `<option value="">-- Select Province --</option>` +
            provinces.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    } catch (err) {
        showToast('Failed to load provinces', 'danger');
    }

    provinceSelect.addEventListener('change', async () => {
        const provId = provinceSelect.value;
        resetSelect(districtSelect, '-- Select District --');
        resetSelect(municipalitySelect, '-- Select Municipality --');
        resetSelect(wardSelect, '-- Select Ward --');

        if (!provId) return;

        try {
            const districts = await apiFetch(`/locations/districts/?province=${provId}`);
            setOptions(districtSelect, districts, (d) => `<option value="${d.id}">${d.name}</option>`, '-- Select District --');
            districtSelect.disabled = false;
        } catch (err) {
            showToast('Failed to load districts', 'danger');
        }
    });

    districtSelect.addEventListener('change', async () => {
        const distId = districtSelect.value;
        resetSelect(municipalitySelect, '-- Select Municipality --');
        resetSelect(wardSelect, '-- Select Ward --');

        if (!distId) return;

        try {
            const municipalities = await apiFetch(`/locations/municipalities/?district=${distId}`);
            setOptions(municipalitySelect, municipalities, (m) => `<option value="${m.id}">${m.name} (${m.type_display || m.type || 'Municipality'})</option>`, '-- Select Municipality --');
            municipalitySelect.disabled = false;
        } catch (err) {
            showToast('Failed to load municipalities', 'danger');
        }
    });

    municipalitySelect.addEventListener('change', async () => {
        const muniId = municipalitySelect.value;
        resetSelect(wardSelect, '-- Select Ward --');

        if (!muniId) return;

        try {
            const wards = await apiFetch(`/locations/wards/?municipality=${muniId}`);
            setOptions(wardSelect, wards, (w) => `<option value="${w.id}">Ward No. ${w.ward_number}</option>`, '-- Select Ward --');
            wardSelect.disabled = false;
        } catch (err) {
            showToast('Failed to load wards', 'danger');
        }
    });
}
