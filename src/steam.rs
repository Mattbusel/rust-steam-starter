//! Steam, when this is the Steam build. Without the `steam` feature every
//! method is a no-op, so the rest of the game never needs a `cfg`.
//!
//! The pattern comes from O'BLOCK (Steam app 5357680): one `Steam` value,
//! created before the window, ticked once a frame, and asked to do small
//! things (unlock, presence, stats) from game code.

/// Your Steam App ID. 480 is Spacewar, Valve's public test app: every Steam
/// account can use it, and it already has achievements and stats defined, so
/// the integration works before you have paid for your own app.
///
/// Replace it with your own App ID (and the number in steam_appid.txt) once
/// Steamworks gives you one.
#[allow(dead_code)]
pub const APP_ID: u32 = 480;

/// Achievement API names. These are the names you type in Steamworks >
/// Stats & Achievements, not the display names. The one below exists on 480.
pub const ACH_FIRST_WIN: &str = "ACH_WIN_ONE_GAME";

/// An integer stat that exists on 480 ("NumGames"). Use your own names.
pub const STAT_GAMES: &str = "NumGames";

/// Rich presence token from steam/richpresence.vdf. Steam shows the localized
/// string to friends, with %score% filled in from the `score` key.
pub const RP_PLAYING: &str = "#Playing";
pub const RP_MENU: &str = "#Menu";

/// What happened when we asked for Steam at startup.
#[allow(dead_code)]
pub enum Start {
    /// Steam is up. Carry on.
    Ready(Steam),
    /// The game was launched outside Steam and Steam is now relaunching it.
    /// Exit right away; the copy Steam starts is the real one.
    Relaunching,
    /// No Steam (not built with the feature, Steam not running, or the user
    /// does not own the app). The game should still run.
    Off(String),
}

#[cfg(feature = "steam")]
mod real {
    use super::*;
    use std::sync::atomic::{AtomicBool, Ordering};
    use std::sync::{Arc, Mutex};

    type Later = Arc<Mutex<Vec<Box<dyn FnOnce(&steamworks::Client) + Send>>>>;

    pub struct Steam {
        client: steamworks::Client,
        overlay: Arc<AtomicBool>,
        // Dropping a callback handle unregisters the callback, so keep it.
        _overlay_cb: steamworks::CallbackHandle,
        /// Steam calls waiting to be made. steamworks 0.13 holds its
        /// call-result lock while a call-result callback runs, and starting a
        /// new call takes that lock again: a call made inside a callback
        /// deadlocks the game. O'BLOCK froze on exactly this. So callbacks
        /// push their follow-up call here and `tick` runs it afterwards.
        later: Later,
        last_presence: std::cell::RefCell<String>,
    }

    impl Steam {
        /// Call this first thing in `main`, before the window exists: the
        /// overlay hooks the graphics API when Steam initializes, so a window
        /// made earlier may never show it.
        pub fn start() -> Start {
            // If the exe was started by double-clicking it (not from Steam),
            // ask Steam to launch it properly and quit. Skipped for 480, or
            // a stray launch would open Spacewar itself. While steam_appid.txt
            // sits next to the exe (or in the working dir, as with cargo run)
            // Steam always answers "no restart needed".
            if APP_ID != 480 && steamworks::restart_app_if_necessary(steamworks::AppId(APP_ID)) {
                return Start::Relaunching;
            }
            let client = match steamworks::Client::init().or_else(|_| steamworks::Client::init_app(APP_ID)) {
                Ok(c) => c,
                Err(e) => return Start::Off(format!("Steam init failed: {e}")),
            };
            let overlay = Arc::new(AtomicBool::new(false));
            let flag = overlay.clone();
            let cb = client.register_callback(move |o: steamworks::GameOverlayActivated| {
                flag.store(o.active, Ordering::Relaxed);
            });
            Start::Ready(Steam { client, overlay, _overlay_cb: cb, later: Default::default(), last_presence: Default::default() })
        }

        /// Once a frame. Steam delivers callbacks (overlay, stats, call
        /// results) only from here.
        pub fn tick(&self) {
            self.client.run_callbacks();
            let due: Vec<_> = self.later.lock().map(|mut q| std::mem::take(&mut *q)).unwrap_or_default();
            for f in due {
                f(&self.client);
            }
        }

        /// The player's Steam name.
        pub fn name(&self) -> String {
            self.client.friends().name()
        }

        /// Unlock and store at once, so the popup shows now and the unlock
        /// survives a crash. Unlocking twice is harmless.
        pub fn unlock(&self, api_name: &str) {
            let us = self.client.user_stats();
            if us.achievement(api_name).set().is_ok() {
                let _ = us.store_stats();
            }
        }

        /// Add to an integer stat and store it.
        pub fn add_stat(&self, api_name: &str, by: i32) {
            let us = self.client.user_stats();
            let now = us.get_stat_i32(api_name).unwrap_or(0);
            if us.set_stat_i32(api_name, now + by).is_ok() {
                let _ = us.store_stats();
            }
        }

        /// What friends see under your name. `token` is a key from
        /// steam/richpresence.vdf; `vars` fill its %placeholders%. Only sends
        /// when something changed, because Steam rate-limits presence.
        pub fn presence(&self, token: &str, vars: &[(&str, String)]) {
            let key = format!("{token}|{vars:?}");
            if *self.last_presence.borrow() == key {
                return;
            }
            *self.last_presence.borrow_mut() = key;
            let f = self.client.friends();
            for (k, v) in vars {
                f.set_rich_presence(k, Some(v));
            }
            f.set_rich_presence("steam_display", Some(token));
        }

        /// True while the Steam overlay (Shift+Tab) is open. Pause on it.
        pub fn overlay_open(&self) -> bool {
            self.overlay.load(Ordering::Relaxed)
        }

        /// Open a web page in the overlay, e.g. your store page for a
        /// "wishlist the full game" button in a demo.
        #[allow(dead_code)]
        pub fn open_url(&self, url: &str) {
            self.client.friends().activate_game_overlay_to_web_page(url);
        }

        /// Run `f` on the next tick, outside every Steam callback. Use it
        /// inside call-result callbacks (leaderboards, workshop) to start the
        /// next call. See the note on `later`.
        #[allow(dead_code)]
        pub fn defer(&self, f: impl FnOnce(&steamworks::Client) + Send + 'static) {
            if let Ok(mut q) = self.later.lock() {
                q.push(Box::new(f));
            }
        }
    }
}

#[cfg(feature = "steam")]
pub use real::Steam;

#[cfg(not(feature = "steam"))]
pub struct Steam;

#[cfg(not(feature = "steam"))]
impl Steam {
    pub fn start() -> Start {
        Start::Off("built without the steam feature".into())
    }
    pub fn tick(&self) {}
    pub fn name(&self) -> String {
        String::new()
    }
    pub fn unlock(&self, _api_name: &str) {}
    pub fn add_stat(&self, _api_name: &str, _by: i32) {}
    pub fn presence(&self, _token: &str, _vars: &[(&str, String)]) {}
    pub fn overlay_open(&self) -> bool {
        false
    }
    #[allow(dead_code)]
    pub fn open_url(&self, _url: &str) {}
}
