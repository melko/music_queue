var browser = browser || chrome; // compatibility with chrome

var settings = {
    server_url: "http://localhost:5000"
};


// get stored settings
browser.storage.local.get(null, checkStoredSettings);


browser.contextMenus.create({
    id: "send-to-queue",
    title: "Send song to music-queue",
    contexts: ["link"],
});

browser.contextMenus.onClicked.addListener((info, tab) => {
    if (info.menuItemId === "send-to-queue") {
        send_youtube(info.linkUrl);
    }
});


browser.browserAction.onClicked.addListener((tab) => {
    send_youtube(tab.url);
});


// update local settings when something changes
browser.storage.onChanged.addListener((changes, areaName) => {
    // assume areaName is always local for now
    console.log("Storage changed");
    for (var s in changes) {
        console.log(`${s} -> ${changes[s].newValue}`);
        settings[s] = changes[s].newValue;
    }
});


function send_youtube(url) {
    const ytID = youtube_parser(url);

    if (ytID === false) {
        console.log("Not a valid youtube URL");
        return;
    }

    var oReq = new XMLHttpRequest();
    oReq.open("GET", settings.server_url + "/youtube/" + ytID);
    oReq.send();
}


function youtube_parser(url){
    var regExp = /^.*((youtu.be\/)|(v\/)|(\/u\/\w\/)|(embed\/)|(watch\?))\??v?=?([^#\&\?]*).*/;
    var match = url.match(regExp);
    return (match&&match[7].length==11)? match[7] : false;
}


function checkStoredSettings(storedSettings) {
    console.log("Checking stored settings");
    Object.assign(settings, storedSettings);

    // save default if not existent
    if (!storedSettings.server_url) {
        console.log("Restoring server_url");
        browser.storage.local.set(settings);
    }
}


function onError(error) {
    console.error(error);
}
