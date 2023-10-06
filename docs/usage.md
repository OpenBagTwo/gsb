# Using `gsb`

!!! warning "PSA"
    These are instructions for the pre-MVP release
    of `gsb`. Explicitly: these instructions require
    you to explicitly navigate to or the specify the
    path of every save file you want to manage, every
    time you run any command. By v0.1 this should no
    longer be required.

## Locating Your Save Data

Before setting up `gsb` to manage your game saves, you'll
first need to know where your save data is located. This
will, of course, vary wildly based on platform and title, but
many games have
[support pages](https://help.minecraft.net/hc/en-us/articles/4409159214605-Managing-Data-and-Game-Storage-in-Minecraft-Java-Edition-#h_01FGA90Z06DE00GT8E81SWX9SE)
that will tell you where to look,
and many game launchers provide [menu options to open your
save folder](https://yuzu-emu.org/wiki/faq/#how-do-i-add-a-save-to-my-game)
in a file explorer.

## Start tracking with `gsb init`

Once you've located a game you want to save, open a command-line and navigate
to the folder containing your save and run the command [`gsb init`](../cli/#init).
By default, all files in the folder will be tracked, so if you only want to track
certain files or subfolders, specify that using the `--track` flag (or if you
want to ignore nay files matching a certain pattern, use `--ignore`).

!!! tip "Pro Tip"
    While `gsb` does not currently support the ability to separately manage individual
    files located in the same folder,
    [this feature is planned.](https://github.com/OpenBagTwo/gsb/issues/29).
    In the meantime, for games where each save is located within a subfolder (_e.g._
    Minecraft worlds), if you want to manage your saves separately, run `gsb init`
    _inside_ each world folder rather than in your "saves" folder.

## Create a backup with `gsb backup`

When you ran `gsb init` it automatically created your first backup. When you're ready
to create your next one, navigate back to the folder where your save is stored and
run the [`gsb backup`](../cli/#backup) command to create another.

Note that `gsb` has two kinds of backups:

1. "Untagged" backups (created by default) are good for just "checking in" regular gameplay
   where you might want to restore to the last state if, say, a creeper blows up your base.
2. "Tagged" backups (created by supplying the `--tag` argument along with a message) are
   meant to denote specific points you might want to return to later (right before an epic
   boss fight or right before a story branch).

!!! danger "Pro Tip"
    You can overwrite a previous backup using the `--combine` / `-c` flag. And if when
    making a new tagged backup you want to delete all of the untagged backups you've made
    since the last time you used the `--tag` flag, you can use `-cc`, _e.g._
    ```bash
    gsb backup -cc --tag "A backup that's actually important"
    ```

## List your backups using `gsb history`

You can view your list of available backups at any time by navigating to your save's folder
and running [`gsb history`](../cli/#history). By default, this will show the identifiers and
dates of all tagged `gsb`-managed backups, so have a look at the various command-line
options to customize both the list of what you see and the amount of information you get
on each backup.

## Restore a backup with `gsb rewind`

If you want to restore a backup, you can do so via [`gsb rewind`](../cli/#rewind).

??? info "Technical Details"
    In order to keep your backup history linear, technically what happens when you
    "rewind" your save state is that the files at that revision are restored and
    then played forward as a _new_ commit. That way all of your changes since the
    point you rewound to are still in your history (future versions of `gsb` will
    let you clean this up later).

If you don't provide a restore point, the command will prompt you to choose from a list
of recent backups.

## Deleting a backup with `gsb delete`

Use [`gsb delete`](../cli/#delete) to delete any backups you no longer need. Note
that this command doesn't _actually_ delete anything on its own (so you won't
recover any disk space immediately). What it does instead is rewrites your history
to exclude those restore points, thus marking them as "loose." To permanently
delete these backups, you will need to download and install a full
[Git client](https://git-scm.com/downloads) and run a "garbage collect" to prune
these loose objects.

??? danger "Pruning via the Git CLI"
    If you have the Git command-line utility installed, the command to run is:
    ```bash
    git gc --aggressive --prune=now
    ```

## Advanced History Management directly with Git

Behind the curtain, `gsb` runs on [Git](https://git-scm.com/) meaning you can run
any advanced commands you wish on a `gsb`-managed save repo directly via the
`git` CLI or any general-purpose Git tool.
