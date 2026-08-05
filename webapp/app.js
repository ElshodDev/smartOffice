const tg = window.Telegram.WebApp;

// Oynani to'liq ekranga ochish
tg.expand();

// Foydalanuvchi ismini ko'rsatish
const greeting = document.getElementById("greeting");
if (tg.initDataUnsafe && tg.initDataUnsafe.user) {
    greeting.innerText = `Salom, ${tg.initDataUnsafe.user.first_name}!`;
}

// Telegram tugmasi bosilganda botga xabar yuborish
function sendMessage(text) {
    tg.sendData(text);
}

function closeApp() {
    tg.close();
}

// Telegramning asosiy temasi ranglariga moslashish (optional)
document.documentElement.style.setProperty('--tg-theme-bg-color', tg.backgroundColor);
