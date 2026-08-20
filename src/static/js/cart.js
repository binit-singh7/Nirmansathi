/**
 * NirmanSathi Cart Utility JavaScript
 */

async function addToCart(productId, quantity = 1) {
    try {
        const user = getUser();
        if (!user || !getToken()) {
            showToast(_t('login_to_add_cart', 'Please login to add products to your cart.'), 'warning');
            setTimeout(() => { window.location.href = '/login/'; }, 1000);
            return;
        }

        const cart = await apiFetch('/marketplace/cart/add-item/', {
            method: 'POST',
            body: JSON.stringify({ product_id: productId, quantity: quantity })
        });

        showToast(_t('product_added_cart', 'Product added to cart!'), 'success');
        updateCartBadge();
        return cart;
    } catch (err) {
        showToast(err.message || _t('failed_add_cart', 'Failed to add product to cart.'), 'danger');
    }
}

async function removeFromCart(itemId) {
    try {
        const cart = await apiFetch(`/marketplace/cart/remove-item/${itemId}/`, {
            method: 'DELETE'
        });
        showToast(_t('item_removed_cart', 'Item removed from cart.'), 'info');
        updateCartBadge();
        return cart;
    } catch (err) {
        showToast(err.message || _t('failed_remove_cart', 'Failed to remove item.'), 'danger');
    }
}
