import os
from flask import Flask, render_template, redirect, request, url_for, flash, session
from flask_pymongo import PyMongo
from bson.objectid import ObjectId 
import uuid

app = Flask(__name__)

app.config['MONGO_DBNAME'] = 'dcdmpDB'
app.config['MONGO_URI'] = 'mongodb+srv://dcdmpDBUser:PassWord@dcdmp.cs4wp.mongodb.net/dcdmpDB?retryWrites=true&w=majority'
app.secret_key = 'some secret kay'
mongo = PyMongo(app)



def data_for_search_autocomplete():
    return mongo.db.books.find({})


@app.route('/')
def home():
    return render_template(
            "home.html",
            new_released = mongo.db.books.find({'new_released' : True}).limit(4),
            big_img = mongo.db.books.find_one({'show_big' : True}),
            best_selling = mongo.db.books.find({'best_selling' : True}).limit(4),
            autocomplete_data = data_for_search_autocomplete()
        )


@app.route('/add_book')
def add_book():
    lang = mongo.db.languages.find_one()
    return render_template("add_book.html", languages=lang['languages'], autocomplete_data = data_for_search_autocomplete())


################ My List ##################
# Check if user is in session
def check_session():
    if "user" in session and "email" in session:
        return True
    else:
        return False    


# Chelking to see if user is admin
def is_admin(name, email):
    if mongo.db.users.find_one({'user_name' : name, 'user_email' : email, 'admin': True}):
        return True
    else:
        return False    


# Getting current page name
def get_page_name():
    return request.url_rule.endpoint


# Retrieving books from mongodb by users
# This function check from which page the request was made
# and acts accordingly
# If request comes from my_list page than all books getting from db by user
# If request comes other than my_list page then the function check if user is admin
# if so it retrievs all books for admin in added_books page.
# In this case admin is abale to set additional setting to books
def retriev_books_by_user(name,  email, page):
    
    if page != 'my_list':     
        if is_admin(name, email):
            users_books = mongo.db.books.find({})
        else:    
            book_id = mongo.db.users.find_one({'user_name' : name, 'user_email' : email})
            users_books = mongo.db.books.find({'_id' : {'$in' : book_id['added_books']}}) 
    else:
        mylist = mongo.db.users.find_one({'user_name' : name, 'user_email' : email})
        users_books = mongo.db.books.find({'_id' : {'$in' : mylist['my_list'] }})
         
    return users_books



# My List
@app.route('/my_list')
def my_list():
    if check_session():
        name = session['user']
        email = session['email']
        page = get_page_name()
        return render_template('/my_list.html', books=retriev_books_by_user(name, email, page), book_of_day=mongo.db.books.find_one({'book_of_day' : True}))

    return render_template("auth.html")



# Checking if the book is alredy in a user's list
def book_already_is_in_list(name, email, book_id):
    my_list = mongo.db.users.find_one({'user_name' : name, 'user_email' : email})
    if ObjectId(book_id) in my_list['my_list']:
        return True
    else:
        return False    



# Inserting a book in a user's "My List"
@app.route('/insert_in_my_list<book_id>')
def insert_in_my_list(book_id):

    if check_session():
        name = session['user']
        email = session['email']
        page = str(request.args.get('page'))

        if book_already_is_in_list(name, email, book_id):
            flash("This book is already in your list")
            return redirect(url_for(page))

        mongo.db.users.update_one({'user_name' : name, 'user_email' : email}, {'$push' : {'my_list' : ObjectId(book_id)}})
        flash("The book has been added seccessfully in your list")
        return redirect(url_for(page))

    return render_template('auth.html')



@app.route("/contact")
def contact():
    return render_template("contact.html", autocomplete_data = data_for_search_autocomplete())



############## ADDED BOOKS BY USER ############
@app.route('/added_books')
def added_books():
    if check_session():
        page = get_page_name()
        return render_template('/added_books.html', books=retriev_books_by_user(session['user'], session['email'], page), book_of_day=mongo.db.books.find_one({'book_of_day' : True}))

    return render_template("auth.html")


# The most searched book
def most_searched_book():
    books = mongo.db.books.find({})
    books_arr = []
    for book in books:
        books_arr.append(int(book['searched']))
        books_arr.sort()
        most_searched = books_arr[-1]

    return mongo.db.books.find_one({'searched' : most_searched})


# Searched book 
@app.route('/book_search', methods=['POST'])
def book_search():
    if request.method == "POST":
        book_name = request.form.get('book_name')

        #Incrementing search reusult field in mongodb
        #To be able to sort by most searched book
        books = mongo.db.books.find({'title' : book_name})
        for book in books:
            inc = int(book['searched'])
            inc += 1
            mongo.db.books.update_one({'title' : book_name}, {'$set' : {'searched' : int(inc)}})

        # Getting searche results by book names
        searched_books = mongo.db.books.find({'title' : book_name})

    return  render_template("book_search.html", results=searched_books, searched=most_searched_book())

    
# If the user already exists in mongo db so it will be saved onlly in session
# Otherwise it will be added as same as it will be saved in session also
def add_user_in_mongodb(name, email):
    # Adding user in mongodb if he/she is new
    if not mongo.db.users.find_one({'user_name' : name, 'user_email' : email}):
        mongo.db.users.insert_one({
            'user_name' : name ,
            'user_email' : email,
            'added_books' : [],
            'my_list' : [],
            'admin' : False
        })

        session['user'] = name
        session['email'] = email

    # storing user in session
    session['user'] = name
    session['email'] = email   

    return True


################# Authentication ####################
# Log Out function
@app.route('/log_out')
def log_out():
    session.clear()
    return render_template('auth.html')


#Get books IDs
def get_books_id(name, email):
    user = mongo.db.users.find_one({'user_name' : name, 'user_email' : email})
    for u in user:
        book_id = int(u[added_books])
        return book_id


# Authentication page
@app.route('/auth', methods=['POST'])
def auth():

    # Checking if button was submited
    if request.method == 'POST':
        if not request.form['user_name'] and not request.form['user_email']:
            flash("In order to make authentication you must fill all fields")
            redirect(request.url)  

        # Making authentication 
        name = request.form['user_name'] 
        email = request.form['user_email']
        page = 'my_list'
        add_user_in_mongodb(name, email)

        # Rendering template and retrieving books by user      
        return render_template('my_list.html' , books = retriev_books_by_user(name, email, page), book_of_day=mongo.db.books.find_one({'book_of_day' : True}))

    return render_template('auth.html')



@app.route('/single_book_page/<book_id>')
def single_book_page(book_id):
    result = mongo.db.books.find_one({'_id' : ObjectId(book_id)})
    return render_template("single_book_page.html", book=result, autocomplete_data = data_for_search_autocomplete() )    




################ INSERTING IMAGE  ###############

# Checking if file has a extension which is in allowed extensions list
def allowed_filesieze(filesize):

    if int(filesize) <= 0.5 * 1024 * 1024:
        return True
    else:
        return False    


# Checking if image has allowed extension
def allowed_ext(filename):
 
    ext = filename.rsplit('.',1)[1]
    allowed_ext = ['JPG', 'JPEG', 'PNG', 'gif']

    if ext.upper() in allowed_ext:
        return ext
    else:
        return False    


# Generating random filename
def generate_random_img_name():
    r_name = str(uuid.uuid4())
    return r_name


f_name = ''

# Uploading image
def upload_image():

    image = request.files['file']
    # Checking image's settings
    if image.filename == '':
        flash('The image must have a name')
        redirect(request.url)
        return False

    if not allowed_filesieze(request.cookies.get('filesize')):
        flash("The allowed maximum image size is 500 KB ")
        redirect(request.url)
        return False

    if not allowed_ext(image.filename):
        flash("The allowed extensions are PNG, JPG, JPEG, GIF")  
        redirect(request.url)
        return False 
    # Saving image to folder
    img_folder_path = 'static/img/uploaded'
    
    # Removing image when updating page and uploading new image
    if request.url_rule.endpoint == 'update_book':
        os.remove(os.path.join(img_folder_path, request.form.get('old_img')))

    r_f_name = generate_random_img_name() + '.' + allowed_ext(image.filename)
    image.save(os.path.join(img_folder_path, r_f_name))
    global f_name 
    f_name = r_f_name
    return True



# Adding user in database
def adding_user(name, email, book_id):
    # If user is new then adding in database
    if not mongo.db.users.find_one({"user_name" : name, "user_email" : email}):
       mongo.db.users.insert_one({
           "user_name" : name,
           "user_email" : email,
           "added_books" : [book_id]
       })

    else:
       # If user already exists then updating added books list
       user = mongo.db.users.update_one({"user_name" : name, "user_email" : email}, {'$push': {"added_books" : book_id}})



# Insertting image
@app.route('/insert_book', methods=['POST'])
def insert_book():

    if request.method == "POST":
       
        if upload_image():
            
            book_id = ObjectId()
            
            # Adding user in database
            adding_user(request.form['user_name'], request.form['user_email'], book_id)

            # Adding books details in database
            mongo.db.books.insert_one({
                "_id" : book_id,
                'title' : request.form['title'],
                'author' : request.form['author'],
                'released_date' : request.form['released_date'],
                'language' : request.form['language'],
                'price' : request.form['price'],
                'description' : request.form['description'],
                'affiliante_link' : request.form['affiliante_link'],
                'image_name' : str(f_name),
                'searched' : 0,
                'my_list' : [],
                'book_of_day' : False,
                'special_offer' : False,
                'new_released' : False,
                'best_selling' : False,
                'show_big' : False
            })

            flash("The Book Has Been Added Successfully ")    

    return redirect(url_for('add_book'))



############# Deleting books #############

@app.route('/delete_book')
def delete_book():

    # Avoiding a accessing straight from url
    if request.args.get('book_id') and request.args.get('img_name'):

        folder_path = 'static/img/uploaded'
        book_id = request.args.get('book_id')
        img_name = request.args.get('img_name')
        page = request.args.get('page')

        if page == 'my_list':
            field_name = page
            f_msg = 'The Book Has Been Successfully Removed From Your List'
        else:
            field_name = 'added_books'
            # Removing books from mongodb
            mongo.db.books.remove({'_id' : ObjectId(book_id)})
            # Removing image from uploaded folder
            os.remove(os.path.join(folder_path, img_name)) 
            f_msg = 'The Book Has Been Deleted'   

        # Deleting added book's ID from users collection
        mongo.db.users.update({'user_name' : session['user'], 'user_email' : session['email']}, {'$pull' : { str(field_name) : ObjectId(book_id) }})

        flash(f_msg)

        return redirect(url_for(field_name))

    return redirect(url_for('added_books'))



########### EDIT BOOK ##################
@app.route('/edit_book')
def edit_book():

    if check_session():
        if request.args.get('book_id'):
            
            lang = mongo.db.languages.find_one()
            book_id = request.args.get('book_id')
            the_book = mongo.db.books.find_one({'_id' : ObjectId(book_id)})

            return render_template(
                        'edit_book.html', 
                        languages=lang['languages'], 
                        book=the_book,
                        admin=is_admin(session['user'],  session['email'])
                    ) 

        return redirect(url_for('added_books'))

    return render_template('auth.html')




@app.route('/update_book/<book_id>' , methods=['POST'])
def update_book(book_id):
    n_img_name = ''
    if check_session():
        if request.method == 'POST':
            # If the image was changed so uploading new image
            n_img_name = request.form.get('old_img')
            new_img = request.files['file']
            if new_img.filename != '':
                upload_image()
                n_img_name = f_name    
            
            # Checkiing to fiind if user is admin
            admin = is_admin(session['user'], session['email'])
            #Updating data in mongodb
            mongo.db.books.update({'_id' : ObjectId(book_id)},
                {
                    'title' : request.form.get('title'),
                    'author' : request.form.get('author'),
                    'released_date' : request.form.get('released_date'),
                    'language' : request.form.get('language'),
                    'price' : request.form.get('price'),
                    'description' : request.form.get('description'),
                    'affiliante_link' : request.form.get('affiliante_link'),
                    'image_name' : n_img_name,
                    'searched' : int(request.form.get('old_searched')),
                    'book_of_day' :  bool(request.form.get('book_of_day')) if admin else bool(request.form.get('old_book_of_day')),
                    'special_offer' : bool(request.form.get('special_offer')) if admin else bool(request.form.get('old_special_offer')),
                    'new_released' : bool(request.form.get('new_released')) if admin else bool(request.form.get('old_new_released')),
                    'best_selling' : bool(request.form.get('best_selling')) if admin else bool(request.form.get('old_best_selling')),
                    'show_big' : bool(request.form.get('show_big')) if admin else bool(request.form.get('old_show_big'))
                })
            flash("The Book Has Been Successfully Updated") 
            return redirect(url_for('edit_book', book_id=book_id))

    return render_template('auth.html')    



if __name__ == '__main__':
    app.run(host=os.environ.get('IP'),
            port=int(os.environ.get('PORT')),
            debug=True)