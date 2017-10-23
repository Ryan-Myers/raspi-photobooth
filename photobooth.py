#!/usr/bin/python
#-------------------------------------------------------------------------------
# Name:        photobooth
# Purpose:     Program for photoboxes
#
# Author:      VoRoN
#
# Created:     03.10.2017
# Copyright:   (c) VoRoN 2017
# Licence:     MIT
#-------------------------------------------------------------------------------

import os
os.environ['PYGAME_FREETYPE'] = ''
import pygame
import widgets
import json
from PIL import Image, ImageDraw, ImageFont
import threading, thread
import datetime
import camera
import subprocess

WIN32 = (os.name != 'posix')
TMP_FOLDER = 'tmp'
if not WIN32:
	window_prop = pygame.FULLSCREEN
	TMP_FOLDER = '/tmp'

def getFilePath(filename):
	in_tmp_folder = os.path.join(TMP_FOLDER, filename)
	in_img_folder = os.path.join('img', filename)
	in_formats_folder = os.path.join('formats', filename)
	if os.path.exists(in_img_folder):
		return in_img_folder
	if os.path.exists(in_tmp_folder):
		return in_tmp_folder
	if os.path.exists(in_formats_folder):
		return in_formats_folder

SETTINGS = {}
SCENES = []
PHOTO_FORMAT = []
with open('config.json', 'r') as f:
	SCENES = json.loads(f.read())
with open('settings.json', 'r') as f:
	SETTINGS = json.loads(f.read())
for fileName in os.listdir('formats'):
	with open(getFilePath(fileName), 'r') as f:
		frmt = json.loads(f.read())
		if isinstance(frmt, list):
			PHOTO_FORMAT += frmt
		else:
			PHOTO_FORMAT.append(frmt)
		

pygame.init()
pygame.mouse.set_visible(SETTINGS['show_mouse'])

screens = []
current_screen = 0
selected_format = PHOTO_FORMAT[0]

for frmt in PHOTO_FORMAT:
	if frmt['name'] == SETTINGS['print_format']:
		selected_format = frmt

font_cache = widgets.FontCache()
image_cache = widgets.ImageCache()
for item in SCENES:
	screens.append(widgets.Screen(item, font_cache, image_cache))

window_prop = pygame.HWSURFACE
if not WIN32:
	window_prop |= pygame.FULLSCREEN

window = pygame.display.set_mode((800, 480), window_prop, 32)
clock = pygame.time.Clock()

def current_screen_is(name):
	if current_screen >= len(screens):
		return False
	return screens[current_screen].name == name

def previos_screen_is(name):
	if current_screen >= len(screens) or\
		current_screen - 1 < 0:
		return False
	return screens[current_screen - 1].name == name

def set_current_screen(name):
	global current_screen
	for x in xrange(len(screens)):
		if screens[x].name == name:
			current_screen = x
			break

def get_screen_by_name(name):
	for x in xrange(len(screens)):
		if screens[x].name == name:
			return screens[x]
	return None

def next_screen():
	global current_screen
	current_screen += 1

result_file_name = ''

def create_photo(photo_config):
	if not WIN32:
		filepattern = os.path.join(TMP_FOLDER, 'capt%04n.jpg')
		camera.get_all_files(filepattern)
		thread.start_new_thread(camera.delete_all_files, ())
	photo_format = tuple(map(lambda x: photo_config['dpi'] * x, photo_config['format']))
	
	image = Image.new('RGB', photo_format, tuple(photo_config['background_color']))
	
	for item in photo_config['components']:
		item_type = item['type']
		
		if item_type == 'image':
			picture = item
			photo_name = getFilePath(picture['file'])
			photo = Image.open(photo_name)
			photo = photo.resize(tuple(picture['size']))
			photo = photo.convert('RGBA')
			photo = photo.rotate(picture['angle'], expand=True)
			image.paste(photo, tuple(picture['position']), photo)
			del photo
			
		if item_type == 'label':
			text_line = item['text']
			font = ImageFont.truetype(item['font'], item['font_size'])
			d = ImageDraw.Draw(image)
			size = d.textsize(text_line, font)
			
			text = Image.new('RGBA', size, (255, 255, 255, 0))
			dt = ImageDraw.Draw(text)
			dt.text((0, 0), text_line, tuple(item['text_color']), font)
			text = text.rotate(item['angle'], expand=True)
			
			image.paste(text, tuple(item['position']), text)
			
			del d
			del dt
	
	today = datetime.datetime.today()
	path = os.path.join(TMP_FOLDER,'results')
	if not os.path.exists(path):
		os.mkdir(path)
	filename = os.path.join(path, 'result_%s_%s.jpg' %
				(today.date().isoformat(), today.time().strftime('%H-%M-%S')))
	image.save(filename)
	global result_file_name
	result_file_name = filename
	
	if SETTINGS['preview_screen']:
		screen = get_screen_by_name('PreviewScreen')
		preview_picture = screen.getControlByName('preview')
		return image.resize(tuple(preview_picture.size)).transpose(Image.ROTATE_90)
	else:
		return None
			
def capture_photo(number):
	if not WIN32:
		camera.trigger_capture()

TAKE_PHOTO = 4
photo_count = 1
thread_take_photo = None

delayScreen = SETTINGS['delay_screens']

done = False
COLLAGE = None
py_image = None

while done == False:
	for event in pygame.event.get():
		screens[current_screen].onevent(event)		
		if event.type == pygame.KEYUP:
			if event.key == pygame.K_ESCAPE:
				done = True
		if event.type == pygame.QUIT:
			done = True
		if event.type == pygame.MOUSEBUTTONUP and current_screen_is('PreviewScreen')\
			and SETTINGS['preview_screen_delay'] == 0:
			set_current_screen('EndScreen')
			pygame.time.set_timer(pygame.USEREVENT + 1, 5000)

		if event.type == pygame.USEREVENT + 1:
			next_screen()
			
			if current_screen_is('StrikeAPoseScreen'):
				if thread_take_photo != None:
					thread_take_photo.join()
				t = threading.Thread(target=capture_photo, args=(photo_count, ))
				thread_take_photo = t
				t.start()
				pygame.time.set_timer(pygame.USEREVENT + 1, 
										SETTINGS['strike_a_pose_delay'])
			
			if current_screen_is('PreviewScreen') and photo_count < TAKE_PHOTO:
				photo_count += 1
				if photo_count <= TAKE_PHOTO:
					set_current_screen(delayScreen)
					pygame.time.set_timer(pygame.USEREVENT + 1, 1000)
					
			if previos_screen_is('WorkInProgress') and COLLAGE == None:
				pygame.time.set_timer(pygame.USEREVENT + 1, 0)
				if thread_take_photo != None:
					thread_take_photo.join()
				COLLAGE = create_photo(selected_format)
				
				mode = COLLAGE.mode
				size = COLLAGE.size
				data = COLLAGE.tobytes()
				py_image = pygame.image.fromstring(data, size, mode)
				
				if SETTINGS['preview_screen']:
					set_current_screen('PreviewScreen')
				else:
					set_current_screen('EndScreen')
					
				if SETTINGS['preview_screen_delay'] != 0\
					and SETTINGS['preview_screen']:
					pygame.time.set_timer(pygame.USEREVENT + 1,
											SETTINGS['preview_screen_delay'])
											
			if current_screen_is('WorkInProgress') and py_image == None\
				and COLLAGE != None:
					set_current_screen('EndScreen')

			if current_screen_is('PreviewScreen') and photo_count >= TAKE_PHOTO:
				if COLLAGE != None:
					picture = screens[current_screen].getControlByName('preview')
					picture.image = py_image
					py_image = None
				else:
					pygame.time.set_timer(pygame.USEREVENT + 1, 100)
					set_current_screen('WorkInProgress')

			if current_screen_is('EndScreen'):
				pygame.time.set_timer(pygame.USEREVENT + 1,
										SETTINGS['end_screen_delay'])

			if current_screen == len(screens):
				pygame.time.set_timer(pygame.USEREVENT + 1, 0)
				set_current_screen('MainScreen')
				
		if event.type == widgets.Button.EVENT_BUTTONCLICK:
			if event.name == 'btnStartClick':
				if not WIN32:
					camera.check_and_close_gvfs_gphoto()
				set_current_screen(delayScreen)
				pygame.time.set_timer(pygame.USEREVENT + 1, 1000)
				photo_count = 1
				thread_take_photo = None
				COLLAGE = None
				py_image = None
				result_file_name = ''
				
			if event.name == 'btnPrintClick':
				print 'Print photo'
				sub = subprocess.Popen(['lp','-d','MITSUBISHI_CPD80D',
								result_file_name],
								stdout=subprocess.PIPE, stderr=subprocess.PIPE,
								shell=False)
				err = sub.stderr.read()
				print err
				
	screens[current_screen].render(window)
	pygame.display.flip()
	clock.tick(60)
pygame.quit()