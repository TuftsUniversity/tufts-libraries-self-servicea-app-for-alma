window.submitFormWithFetch = async function (event, form) {
    event.preventDefault();
    event.stopImmediatePropagation();

    $("#hourglass").show();

    const formData = new FormData(form);

    try {
        const response = await fetch(form.action, {
            method: "POST",
            body: formData,
            credentials: "same-origin",
            redirect: "follow"
        });

        if (response.redirected) {
            $("#hourglass").hide();
            alert("Session expired. Please log in again.");
            window.location.href = response.url;
            return;
        }

        if (!response.ok) throw new Error("Network response was not ok");

        const disposition = response.headers.get("Content-Disposition");
        if (!disposition || !disposition.includes("filename=")) {
            throw new Error("Unexpected response");
        }

        const filename = disposition.split("filename=")[1].replace(/['"]/g, "");
        const blob = await response.blob();

        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = filename;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);

    } catch (err) {
        alert("Error downloading file: " + err.message);
    } finally {
        $("#hourglass").hide();
    }
};
