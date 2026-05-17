#!/bin/bash
#
# Author: Juha Leivo
# Version: 1.1.0
# Date: 2026-05-17
#
# Deploy script(s) to server, updating only if changed.
#
# History
#   1.1.0 - 2026-05-17, add directory support with tar over ssh
#   1.0.0 - 2026-05-17, based on 1.2.1 version of deploy.sh, updated to deploy speech2text

tgt_server="tuvlnxsrvp04.intra.leivo"
ssh_user="juha"
# files_to_update can contain space-separated entries. Each entry may be:
#   src                 -> file: copied to remote as ~/.local/bin/$(basename src)
#                        -> dir: synced to remote as ~/.local/share/$(basename src)
#   src:dest            -> copied/synced to remote path 'dest' (as provided)
# Local src paths may be absolute or relative to this repository root.
# Directories are synced with tar over ssh; files use md5sum + scp.
files_to_update='src/:/srv/speech2text src/main.py:/srv/speech2text/main.py src/requirements.txt:/srv/speech2text/requirements.txt'

# test can one connect
if ping -c 1 -W 1 $tgt_server |grep "^rtt" > /dev/null; then
    echo "$tgt_server is reachable"
else
    echo "Error: $tgt_server is not reachable"
    exit 1
fi

# Default to dry-run. Pass --apply or --commit to perform changes.
DRY_RUN=1
while [ "$#" -gt 0 ]; do
    case "$1" in
        --apply|--commit)
            DRY_RUN=0
            shift ;;
        --help|-h)
            echo "Usage: $0 [--apply|--commit]"
            echo "Default is dry-run (no changes). Use --apply to perform changes."
            exit 0
            ;;
        *)
            echo "Unknown argument: $1"
            exit 1
            ;;
    esac
done

# get remote home directory for correct absolute paths (do it even in dry-run so we can show expanded paths)
remote_home=$(ssh "$ssh_user@$tgt_server" 'echo $HOME' 2>/dev/null || echo "")
if [ -z "$remote_home" ]; then
    echo "Error: could not determine remote HOME for $tgt_server"
    exit 1
fi

declare -a failures=()
declare -a planned_actions=()
declare -a performed_actions=()
declare -A ensured_dirs=()

# Helper: resolve local path to an absolute path inside this repo when possible
repo_root="$(cd "$(dirname "$0")" && pwd)"

for entry in $files_to_update; do
    # parse src:dest or plain src
    src="$entry"
    dest=""
    if [[ "$entry" == *":"* ]]; then
        src="${entry%%:*}"
        dest="${entry#*:}"
    fi

    # if src is relative, make it relative to repo_root
    if [[ ! "$src" = /* ]]; then
        src="$repo_root/$src"
    fi

    if [ ! -e "$src" ]; then
        msg="source $src does not exist, skipping"
        echo "Warning: $msg"
        failures+=("$msg")
        continue
    fi

    # detect if source is a directory
    is_dir=0
    if [ -d "$src" ]; then
        is_dir=1
    fi

    # default remote destination if not provided
    if [ -z "$dest" ]; then
        if [ $is_dir -eq 1 ]; then
            dest="$HOME/.local/share/$(basename "$src")"
        else
            dest="$HOME/.local/bin/$(basename "$src")"
        fi
    fi

    echo "Checking $src -> $dest"

    # expand leading ~ to remote_home so we have absolute remote paths
    if [[ "$dest" == ~* ]]; then
        dest="${dest/#~/$remote_home}"
    fi

    # determine remote target path and remote directory
    if [[ "$dest" == */ ]]; then
        # dest is a directory (possibly with trailing slash)
        remote_dir="${dest%/}"
        remote_target="$remote_dir/$(basename "$src")"
    else
        remote_target="$dest"
        # derive directory portion
        remote_dir="$(dirname "$dest")"
    fi

    # If dest was empty (shouldn't happen here), fallback
    if [ -z "$remote_target" ]; then
        if [ $is_dir -eq 1 ]; then
            remote_target="$HOME/.local/share/$(basename "$src")"
            remote_dir="$HOME/.local/share"
        else
            remote_target="$HOME/.local/bin/$(basename "$src")"
            remote_dir="$HOME/.local/bin"
        fi
    fi

    # Ensure remote target directory exists (or plan to)
    dir_needs_sync=0
    # For directories, check if remote_target exists; for files, check parent directory remote_dir
    if [ $is_dir -eq 1 ]; then
        check_path="$remote_target"
    else
        check_path="$remote_dir"
    fi
    # Skip if we already planned/created this directory in a previous iteration
    if [ -z "${ensured_dirs[$check_path]+x}" ]; then
        # shellcheck disable=SC2029
        if ssh "$ssh_user@$tgt_server" "[ -d $check_path ]"; then
            # Directory already exists; no action needed
            :
        else
            planned_actions+=("ensure remote directory $check_path on $tgt_server")
            if [ $DRY_RUN -eq 0 ]; then
                if ! mkdir_out=$(ssh "$ssh_user@$tgt_server" "mkdir -p $check_path" 2>&1); then
                    msg="Failed to create remote directory $check_path on $tgt_server: $mkdir_out"
                    echo "Error: $msg"
                    failures+=("$msg")
                    continue
                fi
                performed_actions+=("created remote directory $check_path on $tgt_server")
            fi
            # Directory is new, so we always need to sync (only relevant for directories)
            if [ $is_dir -eq 1 ]; then
                dir_needs_sync=1
            fi
        fi
        ensured_dirs["$check_path"]=1
    fi

    if [ $is_dir -eq 1 ]; then
        # Directory handling: use tar over ssh (rsync may not be available)
        # Normalize source path: ensure trailing slash
        dir_src="${src%/}/"

        if [ $dir_needs_sync -eq 1 ]; then
            # Directory is new, always plan/perform full sync
            echo "Copying directory $(basename "$src") to $tgt_server:$remote_target"
            planned_actions+=("sync $src -> $tgt_server:$remote_target/")
            if [ $DRY_RUN -eq 0 ]; then
                # shellcheck disable=SC2029
                if ! tar_out=$(tar -C "$src" -cf - . | ssh "$ssh_user@$tgt_server" "cd $remote_target && tar -xf -" 2>&1); then
                    msg="tar sync failed for $src -> $remote_target: $tar_out"
                    echo "Error: $msg"
                    failures+=("$msg")
                    continue
                fi
                performed_actions+=("synced $src -> $tgt_server:$remote_target/")
            fi
        else
            # Directory exists, check for changes by comparing file lists and checksums
            local_checksums=$(cd "$dir_src" && find . -type f -exec md5sum {} + | sort)
            # shellcheck disable=SC2029
            remote_checksums=$(ssh "$ssh_user@$tgt_server" "cd $remote_target && find . -type f -exec md5sum {} + 2>/dev/null | sort" || echo "")

            if [ "$local_checksums" = "$remote_checksums" ]; then
                echo "$(basename "$src") on $tgt_server is up to date"
            else
                echo "Copying updated directory $(basename "$src") to $tgt_server:$remote_target"
                planned_actions+=("sync $src -> $tgt_server:$remote_target/")
                if [ $DRY_RUN -eq 0 ]; then
                    # shellcheck disable=SC2029
                    if ! tar_out=$(tar -C "$src" -cf - . | ssh "$ssh_user@$tgt_server" "cd $remote_target && tar -xf -" 2>&1); then
                        msg="tar sync failed for $src -> $remote_target: $tar_out"
                        echo "Error: $msg"
                        failures+=("$msg")
                        continue
                    fi
                    performed_actions+=("synced $src -> $tgt_server:$remote_target/")
                fi
            fi
        fi
    else
        # File handling: use md5sum comparison and scp
        # compute local md5
        src_md5=$(md5sum "$src" | awk '{print $1}')

        # compute remote md5 for the target path (silently handle missing file)
        # shellcheck disable=SC2029
        remote_md5=$(ssh "$ssh_user@$tgt_server" md5sum "$remote_target" 2>/dev/null | awk '{print $1}' || echo "")

        if [ -z "$remote_md5" ] || [ "$remote_md5" != "$src_md5" ]; then
            # preserve permissions with scp -p
            if [ -x "$src" ]; then
                action_desc="copy $src -> $tgt_server:$remote_target and chmod +x"
            else
                action_desc="copy $src -> $tgt_server:$remote_target"
            fi
            echo "Copying updated $(basename "$src") to $tgt_server:$remote_target"
            planned_actions+=("$action_desc")
            if [ $DRY_RUN -eq 0 ]; then
                if ! scp_out=$(scp -p "$src" "$ssh_user@$tgt_server":"$remote_target" 2>&1); then
                    original_msg="scp failed for $src -> $remote_target: $scp_out"
                    echo "Error: $original_msg"
                    # Attempt fallback: copy to /tmp and move with sudo (interactive sudo prompt)
                    fallback_target="/tmp/$(basename "$src")"
                    echo "Attempting fallback copy to $tgt_server:$fallback_target"
                    if scp_fallback_out=$(scp -p "$src" "$ssh_user@$tgt_server":"$fallback_target" 2>&1); then
                        echo "Fallback copy succeeded, moving to final destination with sudo"
                        # Allocate a pseudo-tty for sudo password prompt
                        if ! ssh -t "$ssh_user@$tgt_server" "sudo mv $fallback_target $remote_target"; then
                            fallback_msg="fallback sudo mv failed for $fallback_target -> $remote_target"
                            echo "Error: $fallback_msg"
                            failures+=("$original_msg" "$fallback_msg")
                        else
                            # preserve permissions after sudo mv
                            if [ -x "$src" ]; then
                                # shellcheck disable=SC2029
                                ssh "$ssh_user@$tgt_server" "sudo chmod +x $remote_target"
                            fi
                            performed_actions+=("fallback copy and sudo mv $fallback_target -> $remote_target")
                        fi
                    else
                        fallback_msg="fallback scp also failed for $src -> $fallback_target: $scp_fallback_out"
                        echo "Error: $fallback_msg"
                        failures+=("$original_msg" "$fallback_msg")
                    fi
                    continue
                fi
                performed_actions+=("copied $src -> $tgt_server:$remote_target")
                # only chmod +x if source is executable
                if [ -x "$src" ]; then
                    # shellcheck disable=SC2029
                    if ! chmod_out=$(ssh "$ssh_user@$tgt_server" chmod +x "$remote_target" 2>&1); then
                        msg="chmod failed for $remote_target on $tgt_server: $chmod_out"
                        echo "Warning: $msg"
                        failures+=("$msg")
                    else
                        performed_actions+=("chmod +x $remote_target on $tgt_server")
                    fi
                fi
            fi
        else
            echo "$(basename "$src") on $tgt_server is up to date"
        fi
    fi
done

echo
if [ $DRY_RUN -eq 1 ]; then
    echo "Dry-run summary: planned actions (${#planned_actions[@]}):"
    for a in "${planned_actions[@]}"; do
        echo " - $a"
    done
    if [ ${#failures[@]} -ne 0 ]; then
        echo
        echo "Dry-run noted ${#failures[@]} issue(s):"
        for f in "${failures[@]}"; do
            echo " - $f"
        done
        exit 2
    else
        echo
        echo "Dry-run complete: no immediate errors detected"
        exit 0
    fi
else
    echo "Execution summary: performed actions (${#performed_actions[@]}):"
    for a in "${performed_actions[@]}"; do
        echo " - $a"
    done
    if [ ${#failures[@]} -ne 0 ]; then
        echo
        echo "Deployment completed with ${#failures[@]} failure(s):"
        for f in "${failures[@]}"; do
            echo " - $f"
        done
        exit 2
    else
        echo
        echo "Deployment completed successfully"
        exit 0
    fi
fi
