function applyMask(value, pattern) {
    const digits = value.replace(/\D/g, "");
    let result = "";
    let digitIndex = 0;

    for (const char of pattern) {
        if (char === "0") {
            if (digitIndex >= digits.length) break;
            result += digits[digitIndex++];
        } else {
            if (digitIndex >= digits.length) break;
            result += char;
        }
    }

    return result;
}

const cpfInput = document.getElementById("cpf");
const phoneInput = document.getElementById("phone");
const cepInput = document.getElementById("cep");

cpfInput.addEventListener("input", function () {
    this.value = applyMask(this.value, "000.000.000-00");
});

phoneInput.addEventListener("input", function () {
    this.value = applyMask(this.value, "(00) 00000-0000");
});

cepInput.addEventListener("input", function () {
    this.value = applyMask(this.value, "00000-000");
});
