import logging
import sched
import time
import pandas as pd
from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import Updater, CommandHandler, CallbackContext
from facebook_scraper import get_posts
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import datetime
import pytz
from dotenv import load_dotenv
import os

load_dotenv()  # take environment variables from .env.

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)

logger = logging.getLogger(__name__)
# global variables

df_st_relevant = pd.DataFrame()
positive_vibes = pd.DataFrame()
negative_vibes = pd.DataFrame()
happiness_index = 0
curr = datetime.datetime.now()
last_scraped = pytz.timezone('Asia/Singapore').localize(curr).strftime('%Y-%m-%d at %H:%M:%S')
next_scrape = pytz.timezone('Asia/Singapore').localize(curr + datetime.timedelta(hours=3)).strftime(
    '%Y-%m-%d at %H:%M:%S')


#
#
def help(update: Update, context: CallbackContext) -> None:
    "send a message when command help is issued"
    s = "Hey there! Welcome to ST Comments bot!\n\nWhat this is:\nBased on the Facebook comments of the Straits Times page, we will collate the top 5 good news and bad news for your viewing!\n\nDisclaimer:\nWhether a piece of news is good (positive) or bad (negative) is subject to the opinions of Facebook commenters.\n\nMore information:\nhttps://devpost.com/software/straits-times-comments-sentiment-bot"
    update.message.reply_text(s)
    reply_keyboard = [["/goodvibes", "/badvibes", "/help"]]
    update.message.reply_text("More Commands:",
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))


# Define a few command handlers. These usually take the two arguments update and
# context.
def start(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /start is issued."""
    reply_keyboard = [["/goodvibes", "/badvibes"]]
    update.message.reply_text("Hi, what kind of news do you want to read today?",
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))


def goodvibes(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /goodvibes is issued."""
    if len(positive_vibes) == 0:
        update.message.reply_text("No good vibes right now!")
    else:
        update.message.reply_text("Here are your good vibes!")
        for i in range(min(5, len(positive_vibes))):
            value = positive_vibes.iloc[i]
            update.message.reply_text(value.link)
    t = "Data last updated at: " + str(last_scraped) + "\nNext updating time: " + str(next_scrape)
    update.message.reply_text(t)
    reply_keyboard = [["/goodvibes", "/badvibes", "/help"]]
    update.message.reply_text("More Commands:",
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))


def badvibes(update: Update, context: CallbackContext) -> None:
    """Send a message when the command /badvibes is issued."""
    if len(negative_vibes) == 0:
        update.message.reply_text("No bad vibes right now!")
    else:
        update.message.reply_text("Here are your bad vibes!")
        for i in range(min(5, len(negative_vibes))):
            value = negative_vibes.iloc[i]
            update.message.reply_text(value.link)
    t = "Data last updated at: " + str(last_scraped) + "\nNext updating time: " + str(next_scrape)
    update.message.reply_text(t)
    reply_keyboard = [["/goodvibes", "/badvibes", "/help"]]
    update.message.reply_text("More Commands:",
                              reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True))


def comments_to_list(x):
    # list_of_dict = eval(x)
    result = []
    for d in x:
        result.append(d['comment_text'])
    return result


def get_sentiment(x):
    analyzer = SentimentIntensityAnalyzer()
    sentiment_dict = analyzer.polarity_scores(x)
    return sentiment_dict


def main() -> None:
    """Start the bot."""
    # Create the Updater and pass it your bot's token.
    # with open('token.txt') as f:
    #     token = f.read()
    #     f.close()

    token = os.getenv("TOKEN")
    updater = Updater(token)

    # Get the dispatcher to register handlers
    dispatcher = updater.dispatcher

    # on different commands - answer in Telegram
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("goodvibes", goodvibes))
    dispatcher.add_handler(CommandHandler("badvibes", badvibes))
    dispatcher.add_handler(CommandHandler("help", help))

    # Start the Bot
    updater.start_polling()

    # Start scheduled scraping
    s = sched.scheduler(time.time, time.sleep)

    def scrape_data():
        global df_st_relevant
        global positive_vibes
        global negative_vibes
        global happiness_index
        global curr
        global last_scraped
        global next_scrape
        curr = datetime.datetime.now() + datetime.timedelta(hours=8)
        last_scraped = pytz.timezone('Asia/Singapore').localize(curr).strftime('%Y-%m-%d at %H:%M:%S')
        next_scrape = pytz.timezone('Asia/Singapore').localize(curr + datetime.timedelta(hours=3)).strftime(
            '%Y-%m-%d at %H:%M:%S')
        page_name = 'TheStraitsTimes'
        df_list = []
        for post in get_posts(page_name, cookies="cookie.txt", extra_info=False,
                              pages=4, options={"comments": True, "allow_extra_requests": True, "progress": True,
                                                "reactors": False, "posts_per_page": 15}):
            post_entry = post
            # fb_post_df = pd.DataFrame.from_dict(post_entry, orient='index')
            # fb_post_df = fb_post_df.transpose()
            df_list.append(post_entry)

        df_st_relevant = pd.DataFrame(df_list)

        print(df_st_relevant.shape)

        df_st_relevant['comments_full'] = df_st_relevant['comments_full'].apply(comments_to_list)
        df_st_relevant = df_st_relevant[["post_id", "post_text", "post_url", "link", "comments", "comments_full"]]
        # For sentiment column
        sentiment_list_all = []

        # For score column
        scores_list_all = []

        # To get overall SG Happiness

        total_comments = 0

        # Iterate over all posts
        for comment_list in df_st_relevant.comments_full:
            # Reset values for each post
            sum = 0
            sentiment_list_per_post = []
            # Iterate over all comments for each post
            for comments in comment_list:
                value = get_sentiment(comments)
                sentiment_list_per_post.append(value)
                sum += value['compound']
                total_comments += 1
                happiness_index += value['compound']
            # Appends sentiments(for each post) to main list
            sentiment_list_all.append(sentiment_list_per_post)

            # Appends total score for each post
            if len(sentiment_list_per_post) == 0:
                scores_list_all.append(0.0)
            else:
                scores_list_all.append(sum)

        df_st_relevant["sentiment analysis"] = sentiment_list_all
        df_st_relevant["scores"] = scores_list_all
        if total_comments != 0:
            happiness_index = happiness_index / total_comments
        positive_vibes = df_st_relevant[df_st_relevant['scores'] > 0]
        positive_vibes = positive_vibes[positive_vibes['link'].apply(lambda x: True if x.find("t.me") == -1 else False)]
        if not positive_vibes.empty:
            positive_vibes = positive_vibes.sort_values('scores', False)
        negative_vibes = df_st_relevant[df_st_relevant['scores'] < 0]
        negative_vibes = negative_vibes[negative_vibes['link'].apply(lambda x: True if x.find("t.me") == -1 else False)]
        if not negative_vibes.empty:
            negative_vibes = negative_vibes.sort_values('scores', False)
        s.enter(10800, 1, scrape_data)

    scrape_data()
    s.run()

    # Run the bot until you press Ctrl-C or the process receives SIGINT,
    # SIGTERM or SIGABRT. This should be used most of the time, since
    # start_polling() is non-blocking and will stop the bot gracefully.
    updater.idle()


if __name__ == '__main__':
    main()