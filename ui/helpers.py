import streamlit as st
import time

def display_chat(messages):
    """Display the chat messages."""
    for msg in messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                if msg.get("image"):
                    st.image(msg["image"], use_container_width=True)
                if msg.get("video"):
                    st.video(msg["video"])

def run_fake_progress_until_event(event, total_time=75.0, update_interval=0.5):
    """Run a non-linear progress bar that stops once the event is set."""
    progress_bar = st.progress(0)
    message_placeholder = st.empty()
    iterations = int(total_time / update_interval)
    for i in range(iterations):
        if event.is_set():
            progress_bar.progress(100)
            message_placeholder.markdown("**Done!**")
            return
        t = i * update_interval
        fraction = 1 - (1 - t / total_time) ** 3
        percent = min(int(fraction * 100), 99)
        progress_bar.progress(percent)
        if percent < 20:
            message = "Start: Making magic"
        elif percent < 40:
            message = "Concept art happening in the background."
        elif percent < 60:
            message = "Involving top artists on this design"
        elif percent < 70:
            message = "Adding some lights"
        elif percent < 90:
            message = "Nearly finished, it's looking amazing"
        else:
            message = "Get ready, you're gonna like this!"
        message_placeholder.markdown(f"**{message}**")
        time.sleep(update_interval)
    progress_bar.progress(100)
    message_placeholder.markdown("**Done!**")
