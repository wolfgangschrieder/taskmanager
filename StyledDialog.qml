import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    modal: true
    padding: 24
    spacing: 16
    palette.windowText: "#edf5ff"
    palette.text: "#edf5ff"
    palette.buttonText: "#edf5ff"
    palette.placeholderText: "#8298b4"
    palette.highlight: "#61bfff"
    background: Rectangle {
        color: "#152337"
        radius: 20
        border.color: "#3b5877"
        border.width: 1
        Rectangle {
            anchors.fill: parent
            anchors.margins: 1
            radius: 19
            color: "transparent"
            border.color: "#243d56"
        }
    }
    Overlay.modal: Rectangle { color: "#b9000610" }
    header: Rectangle {
        implicitHeight: 74
        color: "transparent"
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 1
            color: "#30465e"
        }
        Column {
            anchors.left: parent.left
            anchors.leftMargin: 24
            anchors.verticalCenter: parent.verticalCenter
            spacing: 5
            Text {
                text: dialog.title
                color: "#f0f5ff"
                font.pixelSize: 20
                font.bold: true
            }
            Text {
                text: "MANAGER HELPER  /  v1.1"
                color: "#7e9cba"
                font.pixelSize: 10
                font.letterSpacing: 1.2
            }
        }
    }
    footer: DialogButtonBox {
        id: actions
        padding: 18
        spacing: 12
        background: Rectangle { color: "transparent" }
        standardButtons: dialog.standardButtons
        onAccepted: dialog.accept()
        onRejected: dialog.reject()
        delegate: Button {
            id: actionButton
            implicitWidth: 128
            implicitHeight: 40
            font.pixelSize: 13
            font.weight: Font.DemiBold
            contentItem: Text {
                text: actionButton.text === "Save" ? "Сохранить" : actionButton.text === "Cancel" ? "Отмена" : actionButton.text === "OK" ? "Создать" : actionButton.text
                color: "#f0f5ff"
                font: actionButton.font
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
            }
            background: Rectangle {
                radius: 10
                color: actionButton.down ? "#305d80" : actionButton.hovered ? "#2d4f6d" : "#213a54"
                border.color: actionButton.hovered ? "#71c6ff" : "#3c5c7c"
            }
        }
    }
}
