var updateBtns = document.getElementsByClassName('update-cart')
for (i = 0; i < updateBtns.length; i++){
    updateBtns[i].addEventListener('click', function(){
        var productId = this.dataset.product;
        var action = this.dataset.action;
        console.log('Product ID:', productId);
        console.log('Action:', action);
        console.log('User:', user); // Biến user được lấy từ base.html
        if (user === 'AnonymousUser'){ // Nếu chưa đăng nhập
            console.log('User is not authenticated');
            alert('Bạn cần đăng nhập để thêm vào giỏ hàng');
        } else { // Nếu đã đăng nhập
            console.log('User is authenticated, sending data...');
            updateUserOrder(productId, action);   // 🔹 THÊM DÒNG NÀY
        }
    });
}

function updateUserOrder(productId, action){
    console.log('User logged in')
    var url = '/update_item/'  // URL cần gửi đến
    fetch(url, {
        method: 'POST',
        headers:{
            'Content-Type':'application/json',
            'X-CSRFToken': csrftoken    , // csrftoken lấy từ base.html
        },
        body: JSON.stringify({'productId': productId, 'action': action}) // chuyển đổi dữ liệu sang JSON
    })
    .then((response) => {
        return response.json(); // chuyển đổi về JSON
    })
    .then((data) => {
        console.log('Data:', data) // in ra console để kiểm tra
        location.reload() // tải lại trang
    })
}