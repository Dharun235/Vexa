" Vim syntax file for Vexa (.vexa)
if exists("b:current_syntax") | finish | endif

syn keyword vexaKeyword if else end for each in define return let const param try break continue
syn keyword vexaKeyword repeat times while expect use as where and or not every second seconds
syn keyword vexaKeyword by to between with confidence
syn keyword vexaConstant true false it detections first last largest smallest nearest farthest
syn keyword vexaConstant all image frame tracks change
syn keyword vexaCommand load detect locate segment count draw print show record save csv ocr scan
syn keyword vexaCommand find inspect check measure reference rotate flip resize scale crop move
syn keyword vexaCommand style translate estimate rank export blur pixelate caption colour color
syn keyword vexaCommand remove background zone zones track compare
syn keyword vexaType number text bool object objects list map contained
syn match vexaAnnotation "\(:\|->\)\s*\(number\|text\|bool\|objects\=\|list\|map\)\>" contains=vexaType
syn match vexaNumber "\<\d\+\(\.\d\+\)\=\>"
syn match vexaFunction "\<\h\w*\ze("
syn match vexaDefine "^\s*define\s\+\zs\h\w*"
syn region vexaInterpolation start="{" end="}" contained contains=vexaNumber,vexaFunction,vexaConstant
syn region vexaString start=+"+ skip=+\\.+ end=+"+ contains=vexaInterpolation,vexaEscape
syn match vexaEscape "\\.\|{{\|}}" contained
syn match vexaComment "#.*$"

hi def link vexaKeyword Keyword
hi def link vexaConstant Constant
hi def link vexaCommand Statement
hi def link vexaType Type
hi def link vexaNumber Number
hi def link vexaFunction Function
hi def link vexaDefine Function
hi def link vexaString String
hi def link vexaEscape SpecialChar
hi def link vexaInterpolation Special
hi def link vexaComment Comment

let b:current_syntax = "vexa"
