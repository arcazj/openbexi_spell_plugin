// SPDX-License-Identifier: GPL-3.0-or-later
package org.openbexi.spell;

import com.google.gson.JsonObject;
import com.intellij.openapi.Disposable;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.fileEditor.OpenFileDescriptor;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.wm.*;
import com.intellij.ui.JBColor;
import com.intellij.ui.components.*;
import com.intellij.ui.content.ContentFactory;
import com.intellij.ui.table.JBTable;
import com.intellij.util.ui.JBUI;
import java.awt.*;
import java.awt.event.*;
import java.time.*;
import java.time.format.DateTimeFormatter;
import javax.swing.*;
import javax.swing.table.*;

/** Theme-aware procedure workspace following SPELL GUI manual sections 3 and 5. */
public final class SpellToolWindow implements ToolWindowFactory {
    @Override public void createToolWindowContent(Project project, ToolWindow window) {
        var view = new View(project);
        var content = ContentFactory.getInstance().createContent(view, "Procedures", false);
        content.setDisposer(view); window.getContentManager().addContent(content);
    }
    private static final DateTimeFormatter DATE = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss z").withZone(ZoneId.systemDefault());
    private static String time(String value) {
        try { if (value.matches("\\d{14,}")) return DATE.format(Instant.ofEpochMilli(Long.parseLong(value) / 1000)); }
        catch (RuntimeException ignored) { }
        return value;
    }
    private static final class View extends JPanel implements Disposable {
        private final Project project;
        private final SpellWorkspace workspace;
        private final JLabel title = new JBLabel("Procedure workspace"), status = new JBLabel("Ready"), subtitle = new JBLabel();
        private final HistoryModel historyModel = new HistoryModel();
        private final CodeModel codeModel = new CodeModel();
        private final JBTable history = new JBTable(historyModel), code = new JBTable(codeModel);
        private final JTextArea output = new JTextArea();
        private final JPanel promptPanel = new JPanel(new BorderLayout(8, 8)), promptBody = new JPanel(new BorderLayout(8, 8));
        private final JLabel promptMessage = new JBLabel();
        private final JButton commit = new JButton("Commit"), reset = new JButton("Reset"), abort = new JButton("Abort procedure");
        private JTextField answerField;
        private ButtonGroup options;
        private String selectedAnswer, renderedPrompt = "";
        private SpellWorkspace.Session renderedSession;
        private boolean refreshing;
        View(Project project) {
            super(new BorderLayout(0, 12)); this.project = project; workspace = SpellWorkspace.get(project);
            setBorder(JBUI.Borders.empty(12));
            JPanel heading = new JPanel(new BorderLayout(12, 8));
            title.setFont(title.getFont().deriveFont(Font.BOLD, title.getFont().getSize2D() + 3));
            status.setBorder(JBUI.Borders.empty(4, 10));
            heading.add(title, BorderLayout.WEST); heading.add(status, BorderLayout.EAST);
            JPanel north = new JPanel(new BorderLayout(0, 8)); north.add(heading, BorderLayout.NORTH);
            JPanel controls = new JPanel(new BorderLayout(0, 6));
            subtitle.setForeground(JBColor.GRAY); controls.add(subtitle, BorderLayout.NORTH);
            DefaultActionGroup group = new DefaultActionGroup();
            for (String id : new String[]{"OpenBEXI.Spell.Run", "OpenBEXI.Spell.Debug", "OpenBEXI.Spell.Pause", "OpenBEXI.Spell.Continue", "OpenBEXI.Spell.Step", "OpenBEXI.Spell.Stop"})
                group.add(ActionManager.getInstance().getAction(id));
            var toolbar = ActionManager.getInstance().createActionToolbar("OpenBEXI.Spell.ToolWindow", group, true);
            toolbar.setTargetComponent(this); controls.add(toolbar.getComponent(), BorderLayout.CENTER);
            north.add(controls, BorderLayout.CENTER); add(north, BorderLayout.NORTH);
            history.setSelectionMode(ListSelectionModel.SINGLE_SELECTION); history.setRowHeight(JBUI.scale(30));
            history.setShowGrid(false); history.setIntercellSpacing(new Dimension(0, 0));
            history.getEmptyText().setText("Your procedure runs will appear here");
            history.getColumnModel().getColumn(0).setPreferredWidth(220);
            history.getColumnModel().getColumn(1).setPreferredWidth(210);
            history.getSelectionModel().addListSelectionListener(event -> {
                if (!refreshing && !event.getValueIsAdjusting() && history.getSelectedRow() >= 0)
                    workspace.select(workspace.sessions().get(history.getSelectedRow()));
            });
            code.setSelectionMode(ListSelectionModel.SINGLE_SELECTION); code.setRowHeight(JBUI.scale(27));
            code.setAutoResizeMode(JTable.AUTO_RESIZE_OFF); code.setShowGrid(false);
            code.getEmptyText().setText("Run a procedure to inspect its code and native results");
            int[] widths = {48, 430, 155, 140, 140, 140};
            for (int index = 0; index < widths.length; index++) code.getColumnModel().getColumn(index).setPreferredWidth(JBUI.scale(widths[index]));
            // Keep labeled columns visible even before the tool window receives its first showing event.
            for (JBTable table : new JBTable[]{history, code}) {
                table.setTableHeader(new JTableHeader(table.getColumnModel()));
                table.getTableHeader().setPreferredSize(new Dimension(table.getPreferredSize().width, JBUI.scale(30)));
                table.getTableHeader().setReorderingAllowed(false);
            }
            code.setDefaultRenderer(Object.class, new DefaultTableCellRenderer() {
                @Override public Component getTableCellRendererComponent(JTable table, Object value, boolean selected, boolean focus, int row, int column) {
                    super.getTableCellRendererComponent(table, value, selected, focus, row, column);
                    if (!selected) setBackground(table.getBackground());
                    setBorder(JBUI.Borders.empty(0, 8));
                    setFont(column == 1 ? new Font(Font.MONOSPACED, Font.PLAIN, table.getFont().getSize()) : table.getFont());
                    var session = workspace.selected(); setToolTipText(column == 1 ? String.valueOf(value) : null);
                    if (session != null) {
                        var result = session.lines.get(row + 1);
                        if (result != null && column > 1) setToolTipText(result.fields.toString());
                        if (!selected && session.currentLine == row + 1 && session.active())
                            setBackground(JBColor.namedColor("Table.selectionInactiveBackground", new JBColor(0xe8efff, 0x303c50)));
                    }
                    return this;
                }
            });
            code.addMouseListener(new MouseAdapter() {
                @Override public void mouseClicked(MouseEvent event) {
                    if (event.getClickCount() == 2 && code.getSelectedRow() >= 0 && workspace.selected() != null)
                        new OpenFileDescriptor(project, workspace.selected().file, code.getSelectedRow(), 0).navigate(true);
                }
            });
            output.setEditable(false); output.setFont(new Font(Font.MONOSPACED, Font.PLAIN, output.getFont().getSize()));
            output.setBorder(JBUI.Borders.empty(8)); var tabs = new JBTabbedPane();
            JPanel codePage = new JPanel(new BorderLayout(0, 5));
            var codeScroll = new JScrollPane(code); codeScroll.setColumnHeaderView(code.getTableHeader()); codePage.add(codeScroll, BorderLayout.CENTER);
            var note = new JBLabel("Native results and timestamps. Blank cells have no reported result.");
            note.setForeground(JBColor.GRAY); note.setBorder(JBUI.Borders.emptyTop(4)); codePage.add(note, BorderLayout.SOUTH);
            tabs.addTab("Code & results", codePage); tabs.addTab("Output", new JBScrollPane(output));
            var historyScroll = new JScrollPane(history); historyScroll.setColumnHeaderView(history.getTableHeader());
            JSplitPane split = new JSplitPane(JSplitPane.VERTICAL_SPLIT, historyScroll, tabs);
            split.setBorder(JBUI.Borders.empty()); split.setResizeWeight(.25); split.setDividerLocation(JBUI.scale(140)); add(split, BorderLayout.CENTER);
            promptPanel.setBorder(BorderFactory.createCompoundBorder(BorderFactory.createLineBorder(JBColor.border()), JBUI.Borders.empty(12)));
            JPanel footer = new JPanel(new BorderLayout(8, 8)), buttons = new JPanel(new FlowLayout(FlowLayout.LEFT, 8, 0));
            buttons.add(commit); buttons.add(reset); buttons.add(abort); footer.add(buttons, BorderLayout.NORTH); footer.add(promptMessage, BorderLayout.SOUTH);
            promptPanel.add(promptBody, BorderLayout.CENTER); promptPanel.add(footer, BorderLayout.SOUTH);
            promptPanel.setVisible(false); add(promptPanel, BorderLayout.SOUTH);
            commit.addActionListener(event -> submit());
            reset.addActionListener(event -> {
                if (options != null) options.clearSelection(); selectedAnswer = null;
                if (answerField != null) { answerField.setText(""); answerField.requestFocusInWindow(); }
                promptMessage.setText(" ");
            });
            abort.addActionListener(event -> workspace.stop(workspace.selected()));
            workspace.listen(this::refresh, this); refresh();
        }
        private void submit() {
            var session = workspace.selected(); if (session == null || session.prompt == null) return;
            String answer = options == null ? answerField.getText() : selectedAnswer;
            if (answer == null) { promptMessage.setText("Select an answer first."); return; }
            int type = 0; try { type = Integer.parseInt(SpellWorkspace.string(session.prompt, "DataType")); } catch (NumberFormatException ignored) { }
            if (options == null && (type & 16) != 0 && !answer.matches("[+-]?(?:\\d+(?:\\.\\d*)?|\\.\\d+)(?:[eE][+-]?\\d+)?")) {
                promptMessage.setText("Enter a valid number before committing."); return;
            }
            if (answer.getBytes(java.nio.charset.StandardCharsets.UTF_8).length > 65536) {
                promptMessage.setText("The answer must be smaller than 64 KiB."); return;
            }
            workspace.answer(session, SpellWorkspace.string(session.prompt, "promptId"), answer);
        }
        private void refresh() {
            refreshing = true;
            try {
                var session = workspace.selected(); historyModel.fireTableDataChanged();
                if (session != null) { int index = workspace.sessions().indexOf(session); if (index >= 0) history.setRowSelectionInterval(index, index); }
                title.setText(session == null ? "Procedure workspace" : session.file.getName()); status.setText(session == null ? "Ready" : session.status);
                subtitle.setText(session == null ? "Open a Python procedure, then choose Run or Debug." : session.file.getPresentableUrl());
                subtitle.setToolTipText(subtitle.getText()); codeModel.fireTableDataChanged();
                String text = session == null ? "" : session.output.toString();
                if (!output.getText().equals(text)) {
                    boolean follow = output.getCaretPosition() == output.getDocument().getLength();
                    output.setText(text); if (follow) output.setCaretPosition(output.getDocument().getLength());
                }
                renderPrompt(session);
            } finally { refreshing = false; }
        }
        private void renderPrompt(SpellWorkspace.Session session) {
            JsonObject prompt = session == null ? null : session.prompt; promptPanel.setVisible(prompt != null);
            if (prompt == null) { renderedPrompt = ""; renderedSession = null; return; }
            String identifier = SpellWorkspace.string(prompt, "promptId");
            if (session != renderedSession || !identifier.equals(renderedPrompt)) {
                renderedSession = session; renderedPrompt = identifier; selectedAnswer = null;
                promptBody.removeAll(); answerField = null; options = null;
                JTextArea question = new JTextArea(SpellWorkspace.string(prompt, "Text"));
                question.setEditable(false); question.setOpaque(false); question.setLineWrap(true); question.setWrapStyleWord(true);
                question.setFont(getFont().deriveFont(Font.BOLD)); question.setRows(Math.min(4, Math.max(2, question.getLineCount())));
                promptBody.add(question, BorderLayout.NORTH);
                String labelsText = SpellWorkspace.string(prompt, "OptionValues"), values = SpellWorkspace.string(prompt, "ExpectedValues");
                int type = 0; try { type = Integer.parseInt(SpellWorkspace.string(prompt, "DataType")); } catch (NumberFormatException ignored) { }
                if (!labelsText.isEmpty() || !values.isEmpty() || (type & 64) != 0) {
                    String[] labels = (labelsText.isEmpty() ? values : labelsText).split("\u0004", -1);
                    options = new ButtonGroup(); JPanel choices = new JPanel(); choices.setLayout(new BoxLayout(choices, BoxLayout.Y_AXIS));
                    for (int index = 0; index < labels.length; index++) {
                        String wire = Integer.toString(index);
                        JRadioButton option = new JRadioButton(labels[index].isEmpty() ? "(empty value)" : labels[index]);
                        option.addActionListener(event -> selectedAnswer = wire); options.add(option); choices.add(option);
                    }
                    var scroll = new JBScrollPane(choices); scroll.setBorder(JBUI.Borders.empty());
                    scroll.setPreferredSize(new Dimension(200, JBUI.scale(Math.min(150, labels.length * 28 + 4)))); promptBody.add(scroll, BorderLayout.CENTER);
                } else {
                    answerField = (type & 4096) != 0 ? new JPasswordField() : new JTextField();
                    answerField.setName("SPELL prompt answer"); answerField.getAccessibleContext().setAccessibleName("SPELL prompt answer");
                    answerField.addActionListener(event -> submit());
                    String hint = (type & 16) != 0 ? "Enter a number" : (type & 1024) != 0 ? "Enter a SPELL date, for example 17-Oct-2026 14:30:00" : "Enter your answer";
                    answerField.setToolTipText(hint); promptBody.add(answerField, BorderLayout.CENTER); promptBody.add(new JBLabel(hint), BorderLayout.SOUTH);
                }
                promptBody.revalidate(); promptBody.repaint();
            }
            commit.setEnabled(!session.answering); reset.setEnabled(!session.answering);
            String message = session.error.isBlank() ? session.answering ? "Submitting answer…" : session.reminded ? "The procedure is waiting for your answer." : " " : session.error;
            if (message.isBlank() && "True".equals(SpellWorkspace.string(prompt, "DefaultProvided")))
                message = "Default answer configured by this procedure: " + SpellWorkspace.string(prompt, "Default");
            promptMessage.setText(message);
        }
        @Override public void dispose() { }
        private final class HistoryModel extends AbstractTableModel {
            private final String[] columns = {"Procedure", "Started (local)", "Result", "Mode"};
            @Override public int getRowCount() { return workspace == null ? 0 : workspace.sessions().size(); }
            @Override public int getColumnCount() { return columns.length; }
            @Override public String getColumnName(int column) { return columns[column]; }
            @Override public Object getValueAt(int row, int column) {
                var session = workspace.sessions().get(row);
                return switch (column) { case 0 -> session.file.getName(); case 1 -> DATE.format(session.started);
                    case 2 -> session.status + (session.exitCode == null ? "" : " (" + session.exitCode + ")"); default -> session.mode; };
            }
        }
        private final class CodeModel extends AbstractTableModel {
            private final String[] columns = {"Line", "Procedure code", "Native date & time", "Item", "Value", "Result"};
            @Override public int getRowCount() { return workspace == null || workspace.selected() == null ? 0 : workspace.selected().source.length; }
            @Override public int getColumnCount() { return columns.length; }
            @Override public String getColumnName(int column) { return columns[column]; }
            @Override public Object getValueAt(int row, int column) {
                var session = workspace.selected(); var result = session.lines.get(row + 1);
                if (column == 0) return row + 1; if (column == 1) return session.source[row]; if (result == null) return "";
                return switch (column) { case 2 -> time(result.time); case 3 -> result.item; case 4 -> result.value; default -> result.result; };
            }
        }
    }
}
