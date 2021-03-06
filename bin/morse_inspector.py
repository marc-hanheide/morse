#!/usr/bin/env python3
"""
inspector.py
Provides a GTK GUI showing object positions and allowing their visibility
in the simulation to be changed. This uses pymorse to establish a socket
connection with Morse for the simulation.get_scene_objects and
simulation.set_object_visibility services.
"""

from gi.repository import Gtk
import pymorse
import sys
import json

class MainWindow(Gtk.Window):
    def __init__(self, name, morse):
        super(MainWindow, self).__init__()
        self.connect("delete-event", Gtk.main_quit)
        self.create_gui()
        self.set_title(name)
        self.morse = morse

        # Get the scene objects from morse. Note that this eval could be bad...
        scene_objects = morse.rpc('simulation','get_scene_objects')
        self.populate_tree(scene_objects)

        self.show_all()
        self.set_size_request(250, 400)

    def create_gui(self):
        scroll = Gtk.ScrolledWindow()
        self.tree_store =  Gtk.TreeStore(str, bool, bool, str)
        self.tree_view = Gtk.TreeView(self.tree_store)
        scroll.add(self.tree_view)

        text_renderer = Gtk.CellRendererText()
        column = Gtk.TreeViewColumn("Component", text_renderer, text=0)
        self.tree_view.append_column(column)
        column = Gtk.TreeViewColumn("Visible", text_renderer, text=1)
        self.tree_view.append_column(column)
        column = Gtk.TreeViewColumn("Dynamics", text_renderer, text=2)
        self.tree_view.append_column(column)

        vbox = Gtk.VBox()
        vbox.pack_start(scroll, True, True, 0)
        self.add(vbox)

        select = self.tree_view.get_selection()
        select.connect("changed", self.on_tree_selection_changed)

        vbox2 = Gtk.VBox()
        self.toggle_visible = Gtk.ToggleButton("Visible")
        self.toggle_visible_all = Gtk.ToggleButton("Visible (and children)")
        self.toggle_dynamics = Gtk.ToggleButton("Dynamics")
        self.position_label = Gtk.Label()
        self.orientation_label = Gtk.Label()
        vbox2.pack_start(self.position_label, True, True, 0)
        vbox2.pack_start(self.orientation_label, True, True, 0)
        hbox = Gtk.HBox()
        hbox.pack_start(self.toggle_visible, True, True, 0)
        hbox.pack_start(self.toggle_visible_all, True, True, 0)
        hbox.pack_start(self.toggle_dynamics, True, True, 0)
        vbox2.pack_start(hbox, False, False, 0)
        vbox.pack_start(vbox2, False, False, 0)
        self.toggle_visible.toggle_handle = self.toggle_visible.connect("toggled", self.toggle_visible_clicked, False)
        self.toggle_visible_all.toggle_handle = self.toggle_visible_all.connect("toggled", self.toggle_visible_clicked, True)
        self.toggle_dynamics.toggle_handle = self.toggle_dynamics.connect("toggled", self.toggle_dynamics_clicked)

    def populate_tree(self, scene, parent=None):
        """Fill the tree store with the scene structure
        """
        for key in scene:
            pose = scene[key][1:]
            new_entry = self.tree_store.append(parent, [key, True, True, json.dumps(pose)])
            self.populate_tree(scene[key][0], new_entry)

    def block_toggle_signals(self):
        """Stop the visibility toggle buttons from responding to
        active state_changes """
        self.toggle_visible.handler_block(self.toggle_visible.toggle_handle)
        self.toggle_visible_all.handler_block(self.toggle_visible_all.toggle_handle)
        self.toggle_dynamics.handler_block(self.toggle_dynamics.toggle_handle)


    def unblock_toggle_signals(self):
        """Allow the visibility toggle buttons to respond to
        active state_changes"""
        self.toggle_visible.handler_unblock(self.toggle_visible.toggle_handle)
        self.toggle_visible_all.handler_unblock(self.toggle_visible_all.toggle_handle)
        self.toggle_dynamics.handler_unblock(self.toggle_dynamics.toggle_handle)

    def on_tree_selection_changed(self, selection):
        # Update the pose labels and state of the visibility toggle buttons
        model, treeiter = selection.get_selected()
        if treeiter != None:
            pose = json.loads(model[treeiter][3])
            visible = model[treeiter][1]
            dynamics = model[treeiter][2]
            name = model[treeiter][0]
            self.position_label.set_text("Position: %.2f %.2f %.2f"%tuple(pose[0]))
            self.orientation_label.set_text("Quaternion: %.2f %.2f %.2f %.2f"%tuple(pose[1]))
            self.acting_on = name
            self.acting_on_iter = treeiter
            self.block_toggle_signals()
            self.toggle_visible.set_active(visible)
            all_vis = self.is_all_vis(treeiter)
            self.toggle_visible_all.set_active(all_vis)
            self.toggle_dynamics.set_active(dynamics)
            self.unblock_toggle_signals()

    def toggle_visible_clicked(self, btn, include_children):
        name = self.acting_on
        state =  morse.rpc('simulation', 'set_object_visibility', name,
                           btn.get_active(), include_children)
        state = state == "True"

        if not include_children: # if only setting the one object
            self.tree_store.set_value(self.acting_on_iter, 1, state)
            self.block_toggle_signals()
            all_vis = self.is_all_vis(self.acting_on_iter)
            self.toggle_visible_all.set_active(all_vis)
            self.unblock_toggle_signals()
        else: # changing the visility of all children too
            self.set_treestore_vis_tag(self.acting_on_iter, state)
            self.block_toggle_signals()
            self.toggle_visible.set_active(
                self.toggle_visible_all.get_active() )
            self.unblock_toggle_signals()

    def toggle_dynamics_clicked(self, btn):
        name = self.acting_on
        state =  morse.rpc('simulation', 'set_object_dynamics', name,
                           btn.get_active())
        state = state == "True"
        self.tree_store.set_value(self.acting_on_iter, 2, state)

    def set_treestore_vis_tag(self, treeiter, state, siblings=False):
        """ Change the treestore to show if a item is visible. Optionally
        siblings too"""
        while treeiter != None:
            self.tree_store[treeiter][1] = state
            if self.tree_store.iter_has_child(treeiter):
                childiter = self.tree_store.iter_children(treeiter)
                self.set_treestore_vis_tag(childiter, state, True)
            if not siblings:
                treeiter = None
            else:
                treeiter = self.tree_store.iter_next(treeiter)

    def is_all_vis(self, treeiter, siblings=False): #
        """ Test to see if treeiter and all its children are visible"""
        state = True
        while treeiter != None:
            state = state and self.tree_store[treeiter][1]
            if self.tree_store.iter_has_child(treeiter):
                childiter = self.tree_store.iter_children(treeiter)
                state =  state and self.is_all_vis(childiter, True)
            if not siblings:
                treeiter = None
            else:
                treeiter = self.tree_store.iter_next(treeiter)
        return state

morse = None
try:
    morse = pymorse.Morse()
except ConnectionError as e:
    print ("Can't connect to morse. make sure you started the simulation..")
    sys.exit(1)

window = MainWindow("Morse Objects", morse)


Gtk.main()
morse.close()
