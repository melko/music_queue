var browser = browser || chrome;

function saveOptions(e) {
    e.preventDefault();
    console.log("saving settings");
    browser.storage.local.set({
        server_url: document.querySelector("#server_url").value
    });
}

function restoreOptions() {
    browser.storage.local.get(null, (result) => {
        console.log("refreshing UI");
        document.querySelector("#server_url").value = result.server_url;
    });
}


document.addEventListener("DOMContentLoaded", restoreOptions);
document.querySelector("form").addEventListener("submit", saveOptions);
