import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Dialog {
    id: dialog
    modal: true
    property bool canSubmit: true
    property string confirmLabel: ""
    padding: 24
    spacing: 16
    palette.windowText: "#edf5ff"
    palette.text: "#edf5ff"
    palette.buttonText: "#edf5ff"
    palette.placeholderText: "#8298b4"
    palette.highlight: "#61bfff"
    background: Rectangle {
        color: "#192431"
        radius: 20
        border.color: "#354b61"
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
                text: "MANAGER HELPER  /  1.1"
                color: "#7e9cba"
                font.pixelSize: 10
                font.letterSpacing: 1.2
            }
        }
    }
    footer: Rectangle {
        implicitHeight: dialog.standardButtons === 0 ? 0 : 70
        visible: dialog.standardButtons !== 0
        color: "transparent"
        Row {
            anchors.right: parent.right
            anchors.rightMargin: 20
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12
            Button {
                id: cancelButton
                text: "Отмена"
                width: 120
                height: 40
                onClicked: dialog.reject()
                contentItem: Text {
                    text: cancelButton.text
                    color: "#b4c7df"
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 10
                    color: cancelButton.hovered ? "#30445c" : "#1b2b40"
                    border.color: "#36506b"
                }
            }
            Button {
                id: saveButton
                text: dialog.confirmLabel || ((dialog.standardButtons & Dialog.Ok) !== 0 ? "Создать" : "Сохранить")
                width: 138
                height: 40
                enabled: dialog.canSubmit
                onClicked: dialog.accept()
                contentItem: Text {
                    text: saveButton.text
                    color: "#071827"
                    font.pixelSize: 14
                    font.bold: true
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                }
                background: Rectangle {
                    radius: 10
                    color: saveButton.down ? "#51a6de" : saveButton.hovered ? "#94d8ff" : "#6fc4ff"
                }
            }
        }
    }
}
