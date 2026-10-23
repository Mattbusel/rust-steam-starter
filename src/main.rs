// Release builds on Windows open no console window next to the game.
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

//! A tiny game: move the square, collect coins. Collect 10 and you win, which
//! unlocks an achievement on the Steam build. It exists to show where the
//! Steam calls go; replace it with your game.

mod steam;

use macroquad::prelude::*;
use steam::{Start, Steam};

const GOAL: u32 = 10;

fn conf() -> Conf {
    Conf { window_title: "mygame".to_owned(), window_width: 960, window_height: 540, high_dpi: true, ..Default::default() }
}

fn main() {
    // Steam comes first: before the window, so the overlay can hook it, and
    // before anything slow, so a relaunch through Steam is instant.
    let (steam, status) = match Steam::start() {
        Start::Ready(s) => {
            let who = s.name();
            (Some(s), format!("Steam: signed in as {who}"))
        }
        Start::Relaunching => return,
        Start::Off(why) => (None, format!("Steam: off ({why})")),
    };
    macroquad::Window::from_config(conf(), game(steam, status));
}

struct World {
    player: Vec2,
    coin: Vec2,
    score: u32,
    won: bool,
    seed: u32,
}

impl World {
    fn new() -> World {
        let mut w = World { player: vec2(480.0, 270.0), coin: Vec2::ZERO, score: 0, won: false, seed: 12345 };
        w.coin = w.next_coin();
        w
    }

    // A tiny xorshift so the skeleton needs no rand crate.
    fn next_coin(&mut self) -> Vec2 {
        let mut r = || {
            self.seed ^= self.seed << 13;
            self.seed ^= self.seed >> 17;
            self.seed ^= self.seed << 5;
            (self.seed % 1000) as f32 / 1000.0
        };
        vec2(40.0 + r() * 880.0, 80.0 + r() * 420.0)
    }
}

async fn game(steam: Option<Steam>, status: String) {
    let mut w = World::new();
    loop {
        if let Some(s) = &steam {
            s.tick();
        }
        let paused = steam.as_ref().is_some_and(|s| s.overlay_open());

        if !paused && !w.won {
            let dt = get_frame_time();
            let mut d = Vec2::ZERO;
            if is_key_down(KeyCode::Left) || is_key_down(KeyCode::A) {
                d.x -= 1.0;
            }
            if is_key_down(KeyCode::Right) || is_key_down(KeyCode::D) {
                d.x += 1.0;
            }
            if is_key_down(KeyCode::Up) || is_key_down(KeyCode::W) {
                d.y -= 1.0;
            }
            if is_key_down(KeyCode::Down) || is_key_down(KeyCode::S) {
                d.y += 1.0;
            }
            w.player = (w.player + d.normalize_or_zero() * 320.0 * dt).clamp(vec2(16.0, 16.0), vec2(944.0, 524.0));
            if w.player.distance(w.coin) < 26.0 {
                w.score += 1;
                w.coin = w.next_coin();
                if w.score >= GOAL {
                    w.won = true;
                    if let Some(s) = &steam {
                        s.unlock(steam::ACH_FIRST_WIN);
                        s.add_stat(steam::STAT_GAMES, 1);
                    }
                }
            }
        }
        if w.won && is_key_pressed(KeyCode::Enter) {
            w = World::new();
        }
        if let Some(s) = &steam {
            if w.won {
                s.presence(steam::RP_MENU, &[]);
            } else {
                s.presence(steam::RP_PLAYING, &[("score", w.score.to_string())]);
            }
        }

        // Draw in a fixed 960x540 space, scaled to the window.
        let cam = Camera2D::from_display_rect(Rect::new(0.0, 540.0, 960.0, -540.0));
        set_camera(&cam);
        clear_background(Color::from_rgba(12, 12, 18, 255));
        draw_circle(w.coin.x, w.coin.y, 10.0, GOLD);
        draw_rectangle(w.player.x - 14.0, w.player.y - 14.0, 28.0, 28.0, Color::from_rgba(77, 230, 255, 255));
        draw_text(&format!("COINS {} / {}", w.score, GOAL), 20.0, 36.0, 32.0, WHITE);
        draw_text(&status, 20.0, 520.0, 22.0, GRAY);
        if w.won {
            draw_text("YOU WIN. Achievement unlocked if Steam is on. ENTER to play again.", 120.0, 270.0, 26.0, GOLD);
        }
        if paused {
            draw_text("PAUSED (Steam overlay open)", 330.0, 300.0, 28.0, WHITE);
        }
        next_frame().await;
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn coins_spawn_inside_the_play_area() {
        let mut w = World::new();
        for _ in 0..1000 {
            let c = w.next_coin();
            assert!(c.x >= 40.0 && c.x <= 920.0 && c.y >= 80.0 && c.y <= 500.0, "{c:?}");
        }
    }
}
