import os

target_file = "webcad_xbf/templates/project.html"
backup_file = "webcad_xbf/templates/project.html.before-import-ui"

dialog_id = 'id="collaboration-profile-dialog"'

# Extract dialog from backup or use explicit clean block
dialog_markup = """  <dialog id="collaboration-profile-dialog" class="model-dialog collaboration-profile-dialog">
    <form method="dialog" id="collaboration-profile-form" class="model-shell">
      <header><div><h2>CascadeCAD User</h2><p>Choose your username, presence, and how conservatively the community may describe your active project.</p></div><button value="cancel" class="icon-button" aria-label="Close">×</button></header>
      <div class="model-fields">
        <label>Username <input id="collaboration-username" type="text" minlength="3" maxlength="40" autocomplete="username" required></label>
        <label>Presence <select id="collaboration-status"><option value="available">Available</option><option value="busy">Busy</option><option value="invisible">Invisible</option></select></label>
        <label>Active project visibility <select id="collaboration-project-visibility"><option value="hidden">Hidden — show Private project</option><option value="category">Category only</option><option value="public">Public Showcase — show project name</option></select></label>
        <label>Public category <input id="collaboration-project-category" type="text" maxlength="60" value="CAD project" placeholder="Marine design, mechanical CAD…"></label>
      </div>
      <p class="small-copy">This build provides UUID device sessions and collaboration permissions.</p>
      <footer><button value="cancel" type="button" id="cancel-collaboration-profile" class="secondary">Cancel</button><button value="default" type="submit" class="primary-action">Enter CascadeCAD</button></footer>
    </form>
  </dialog>"""

if os.path.exists(target_file):
    with open(target_file, "r", encoding="utf-8") as f:
        content = f.read()
    
    if dialog_id not in content:
        # Insert before the closing body tag
        if "</body>" in content:
            content = content.replace("</body>", f"\n{dialog_markup}\n</body>")
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(content)
            print("[+] Successfully restored collaboration-profile-dialog into project.html")
        else:
            print("[!] Could not find </body> tag in project.html")
    else:
        print("[*] collaboration-profile-dialog already exists in project.html")

