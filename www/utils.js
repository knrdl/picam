function show(selector, value = true) {
    if (value)
        document.querySelector(selector).removeAttribute("hidden")
    else
        document.querySelector(selector).setAttribute("hidden", "hidden")

}

function id(v) {
    return document.getElementById(v)
}