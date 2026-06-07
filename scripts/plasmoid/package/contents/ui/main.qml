import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PC3
import org.kde.plasma.plasma5support as P5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string launcher: "__LAUNCHER__"
    property bool serverUp: false

    Plasmoid.icon: "__ICON__"
    preferredRepresentation: fullRepresentation

    // Run shell commands (open the app via the launcher).
    P5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: function(source, data) { disconnectSource(source) }
        function run(cmd) { connectSource(cmd) }
    }
    function sh(s) { return "'" + String(s).replace(/'/g, "'\\''") + "'" }
    function open(path) { exec.run("bash " + sh(launcher) + " --path " + sh(path)) }
    function ask(text) { exec.run("bash " + sh(launcher) + " --ask " + sh(text)) }

    // Health poll via XHR.
    Timer {
        interval: 15000; running: true; repeat: true; triggeredOnStart: true
        onTriggered: {
            var x = new XMLHttpRequest();
            x.onreadystatechange = function() {
                if (x.readyState === XMLHttpRequest.DONE) root.serverUp = (x.status === 200);
            };
            try { x.open("GET", "http://127.0.0.1:7000/api/health"); x.timeout = 4000; x.send(); }
            catch (e) { root.serverUp = false; }
        }
    }

    fullRepresentation: ColumnLayout {
        Layout.preferredWidth: Kirigami.Units.gridUnit * 15
        spacing: Kirigami.Units.smallSpacing

        RowLayout {
            Kirigami.Heading { text: "Mentor"; level: 2; Layout.fillWidth: true }
            PC3.Label {
                text: root.serverUp ? "● running" : "○ stopped"
                color: root.serverUp ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor
                font: Kirigami.Theme.smallFont
            }
        }

        QQC2.TextField {
            id: askField
            Layout.fillWidth: true
            placeholderText: "Ask Mentor…"
            onAccepted: { if (text.length) { root.ask(text); text = ""; } }
        }

        RowLayout {
            Layout.fillWidth: true
            QQC2.Button { text: "Open"; Layout.fillWidth: true; onClicked: root.open("/app") }
            QQC2.Button { text: "Office"; Layout.fillWidth: true; onClicked: root.open("/app/office") }
            QQC2.Button { text: "Health"; Layout.fillWidth: true; onClicked: root.open("/manage#diag") }
        }
    }
}
