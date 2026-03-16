// Validátor függvények
function isEmail(email) {
    return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email);
}

function isPhone(phone) {
    return /^[\+\d][\d\s\-\(\)]{8,}$/.test(phone);
}

function notEmpty(str) {
    return str && str.trim().length > 0;
}
