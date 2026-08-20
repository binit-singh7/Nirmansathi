/**
 * Permits JS Utility: Location Cascades & Document File Handling
 */

async function initLocationCascades(provinceSelectId, districtSelectId, municipalitySelectId, wardSelectId) {
    const provinceSelect = document.getElementById(provinceSelectId);
    const districtSelect = document.getElementById(districtSelectId);
    const municipalitySelect = document.getElementById(municipalitySelectId);
    const wardSelect = document.getElementById(wardSelectId);

    if (!provinceSelect || !districtSelect || !municipalitySelect || !wardSelect) return;

    const selectProvText = _t('select_province', '-- Select Province --');
    const selectDistText = _t('select_district', '-- Select District --');
    const selectMuniText = _t('select_municipality', '-- Select Municipality --');
    const selectWardText = _t('select_ward', '-- Select Ward --');
    const wardNoText = _t('ward_no', 'Ward No.');

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
        provinceSelect.innerHTML = `<option value="">${selectProvText}</option>` +
            provinces.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
    } catch (err) {
        showToast(_t('failed_load_provinces', 'Failed to load provinces'), 'danger');
    }

    provinceSelect.addEventListener('change', async () => {
        const provId = provinceSelect.value;
        resetSelect(districtSelect, selectDistText);
        resetSelect(municipalitySelect, selectMuniText);
        resetSelect(wardSelect, selectWardText);

        if (!provId) return;

        try {
            const districts = await apiFetch(`/locations/districts/?province=${provId}`);
            setOptions(districtSelect, districts, (d) => `<option value="${d.id}">${d.name}</option>`, selectDistText);
            districtSelect.disabled = false;
        } catch (err) {
            showToast(_t('failed_load_districts', 'Failed to load districts'), 'danger');
        }
    });

    districtSelect.addEventListener('change', async () => {
        const distId = districtSelect.value;
        resetSelect(municipalitySelect, selectMuniText);
        resetSelect(wardSelect, selectWardText);

        if (!distId) return;

        try {
            const municipalities = await apiFetch(`/locations/municipalities/?district=${distId}`);
            setOptions(municipalitySelect, municipalities, (m) => `<option value="${m.id}">${m.name} (${m.type_display || m.type || 'Municipality'})</option>`, selectMuniText);
            municipalitySelect.disabled = false;
        } catch (err) {
            showToast(_t('failed_load_municipalities', 'Failed to load municipalities'), 'danger');
        }
    });

    municipalitySelect.addEventListener('change', async () => {
        const muniId = municipalitySelect.value;
        resetSelect(wardSelect, selectWardText);

        if (!muniId) return;

        try {
            const wards = await apiFetch(`/locations/wards/?municipality=${muniId}`);
            setOptions(wardSelect, wards, (w) => `<option value="${w.id}">${wardNoText} ${w.ward_number}</option>`, selectWardText);
            wardSelect.disabled = false;
        } catch (err) {
            showToast(_t('failed_load_wards', 'Failed to load wards'), 'danger');
        }
    });
}
