project(hlsl NONE)
cmake_minimum_required(VERSION 3.15)

find_package(LATEX REQUIRED COMPONENTS)

if (NOT MAKEGLOSSARIES_COMPILER)
  get_filename_component(LATEX_DIR ${PDFLATEX_COMPILER} DIRECTORY)
  find_program(MAKEGLOSSARIES_COMPILER makeglossaries HINTS ${LATEX_DIR})
endif()

if (NOT MAKEGLOSSARIES_COMPILER)
  message(FATAL_ERROR "Could not find makeglossaries")
endif()

if (NOT PANDOC_COMPILER)
  find_program(PANDOC_COMPILER pandoc)
endif()

set(intermediate_dir ${CMAKE_BINARY_DIR}/tmp/)

message(STATUS "Generating targets for: ${PROJECT_NAME}")
set(main_file ${CMAKE_CURRENT_SOURCE_DIR}/${PROJECT_NAME}.tex)
set(out_dir ${CMAKE_BINARY_DIR})

add_custom_target(${PROJECT_NAME}-dirs
                  COMMAND ${CMAKE_COMMAND} -E make_directory ${CMAKE_BINARY_DIR}/html
                  COMMENT "Creating directories for ${PROJECT_NAME}")

add_custom_target(${PROJECT_NAME}-prebuild
                  COMMAND ${PDFLATEX_COMPILER}
                            -output-directory ${CMAKE_BINARY_DIR}
                            -draftmode -interaction=nonstopmode
                            ${main_file}
                  COMMENT "Prebuilding ${PROJECT_NAME}"
                  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                  DEPENDS ${main_file} ${PROJECT_NAME}-dirs)
add_custom_target(${PROJECT_NAME}-glossaries
                COMMAND ${MAKEGLOSSARIES_COMPILER} -d ${CMAKE_BINARY_DIR} ${PROJECT_NAME}
                COMMENT "Prebuilding ${PROJECT_NAME} Glossaries"
                WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                DEPENDS ${main_file} ${PROJECT_NAME}-prebuild)
add_custom_target(pdf
                  COMMAND ${PDFLATEX_COMPILER}
                          -output-directory ${CMAKE_BINARY_DIR}
                          ${main_file}
                  # It is not a mistake that this is repeated. TeX compilers are
                  # dumb. The first run generates the ToC and the second run is
                  # required to ensure the references are all correct.
                  COMMAND ${PDFLATEX_COMPILER}
                          -output-directory ${CMAKE_BINARY_DIR}
                          ${main_file}
                  COMMENT "Assembling ${PROJECT_NAME}.pdf"
                  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                  DEPENDS ${main_file} ${PROJECT_NAME}-prebuild ${PROJECT_NAME}-glossaries)

add_custom_target(html
                  COMMAND ${PANDOC_COMPILER} ${main_file} -f latex -t html --table-of-contents=true -s -o ${CMAKE_BINARY_DIR}/html/hlsl.html
                  COMMENT "Generating HTML"
                  WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
                  DEPENDS ${main_file} ${PROJECT_NAME}-prebuild ${PROJECT_NAME}-glossaries ${PROJECT_NAME}-dirs)
