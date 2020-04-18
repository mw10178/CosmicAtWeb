let highlightedObject = $();
let currentFrame = 0;
let navBarHeight;
let ctx;

const drawHole = object => {
    for (let i = 0; i < object.length; i++) {
        const rectangle = object[i].getBoundingClientRect();
        ctx.beginPath();
        ctx.globalCompositeOperation = 'destination-out';
        ctx.lineJoin = "round";
        ctx.lineWidth = 20;
        ctx.rect(rectangle.left - 6, rectangle.top - 6 - navBarHeight, rectangle.width + 12, rectangle.height + 12);
        ctx.fill();
        ctx.stroke();
    }

    const rectangle = $('nav')[0].getBoundingClientRect();
    ctx.beginPath();
    ctx.fillStyle = "rgba(0,0,0,1)";
    ctx.rect(rectangle.left, rectangle.top - navBarHeight, rectangle.width, rectangle.height);
    ctx.globalCompositeOperation = 'destination-out';
    ctx.fill();
    ctx.fillStyle = "rgba(0,0,0,0.5)";
    ctx.globalCompositeOperation = 'destination-over';
    ctx.fill();
    ctx.fillStyle = "rgba(255,255,255,1)";
};

const scrollTo = element => {
    if (element === null || element.length === 0) {
        console.log("Not scrolling");
        return;
    }

    if (element.length > 1) {
        element = $(element[0]);
    }

    $('body, html').animate({scrollTop: $(element).offset().top - window.innerHeight * 0.4}, 600);
    window.setTimeout(() => {
        $('body,html').stop(true, false, true);
    }, 600);
};

const createNewFrame = newFrame => {
    if (newFrame) {
        const data = tutorialData[currentFrame] = Object.assign({}, tutorialData.defaultSettings, tutorialData[currentFrame]);

        const left = data.textPosition.x + 'vw';
        const top = data.textPosition.y + 'vh';
        $('#textwrapper').css({left, top});

        // if explanation or task are empty hide hr
        if (!data.explanation || !data.task) {
            $('hr').hide();
        } else {
            $('hr').show();
        }

        $("#progress").html(`${data.headline} (${currentFrame + 1}) / ${tutorialData.length})`);
        $('#explanation').html(data.explanation);
        $('#task').html(data.task);

        moveExitButton();

        highlightedObject.css('pointer-events', '');

        highlightedObject = $(data.highlightSelector);

        scrollTo(highlightedObject);

        highlightedObject.one('click', () => data.doneOnClick ? userAction(39, true) : null)
            .css('pointer-events', data.highlightDisabled ? 'none' : 'auto');
    }

    drawHole(highlightedObject);
    moveExitButton();
};

const moveExitButton = () => {
    const textWrapper = $("#textwrapper");
    const tbr = parseFloat(textWrapper.css('left')) + parseFloat(textWrapper.css('padding-left')) / 2 + parseFloat(textWrapper.css('width')) / 2 + "px";
    const tbt = parseFloat(textWrapper.css('top')) - parseFloat(textWrapper.css('height')) / 2 - parseFloat(textWrapper.css('padding-top')) / 2 + "px";
    $("#stopTutorial").css({top: tbt, left: tbr});
};

const taskDone = () => {
    const validator = tutorialData[currentFrame].validator ? tutorialData[currentFrame].validator :
        tutorialData.defaultSettings.validator ? tutorialData.defaultSettings.validator : () => true;
    return validator(highlightedObject)
};

const setup = () => {
    if ($('.tutorial:hidden').length === 0) {
        const ctx = document.getElementById('overlay').getContext('2d');
        navBarHeight = $('#navigation')[0].getBoundingClientRect().height;

        $("#overlay").css("top", navBarHeight).css('height', window.innerHeight - navBarHeight);

        ctx.clearRect(0, 0, window.innerWidth, window.innerHeight);
        ctx.canvas.height = window.innerHeight - navBarHeight;
        ctx.canvas.width = window.innerWidth;
        ctx.fillStyle = "rgba(0,0,0,0.5)";
        ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);
        ctx.fillStyle = "rgba(255,255,255,1)";
        $('#content').css('pointer-events', 'none');
        $('nav').css('pointer-events', 'auto');

        const textWrapper = $("#textwrapper");
        const tempDiff = (parseFloat(textWrapper.css('top')) - parseFloat(textWrapper.css('height')) / 2) - parseFloat(textWrapper.css('padding-top')) * 3 - navBarHeight;

        if (tempDiff < 0) {
            textWrapper.css({top: parseFloat(textWrapper.css('top')) - tempDiff});
        }
    }
};

// Listener functions

const redraw = () => {
    setup();
    createNewFrame(false);
};

const drawNewFrame = () => {
    setup();
    createNewFrame(true);

    $('body').focus();
};

// par uses keycodes:
//
// 37 backarrow
// 39 frontarrow
// 71 g for godmode
// 27 esc

const userAction = (par, td) => {
    if (par === 37 && currentFrame > 0) {
        currentFrame--;
        drawNewFrame();
    } else if (par === 39) {
        if (currentFrame < tutorialData.length - 1) {
            if (td) {
                currentFrame++;
                drawNewFrame();
            } else {
                remindOfTask();
            }
        } else {
            stopTutorial();
        }
    } else if (par === 71) {
        currentFrame++;
        drawNewFrame();
    }
    else if (par === 27) {
        stopTutorial();
    }
    else if (par === 67) {
        localStorage.deleteKey('visited');
    }
};

const stopTutorial = () => {
    $('.tutorial').hide();
    $('.popup-background').hide();
    $('#content').css('pointer-events', '');
    $('nav').css('pointer-events', '')
        .removeClass('fixed_tutorial');

    simpleStorage.set('visited', 'true');
};

const remindOfTask = () => {
    const animationLength = 75;

    $('#task').animate({left: '-1vw'}, animationLength)
        .animate({left: '1vw'}, animationLength)
        .animate({left: '0vw'}, animationLength);

    window.setTimeout(() => {
        $('#task').stop(true, true, true)
            .css({left: '0vw'});
    }, animationLength * 4);
};

const startTutorial = () => {
    $(document).click(() => {
        moveExitButton();
    });

    $('#next').click(() => {
        userAction(39, taskDone());
    });

    $('#back').click(() => {
        userAction(37, taskDone());
    });

    $('#stopTutorial').click(() => {
        stopTutorial();
    });

    $(document).keyup(e => {
        userAction(e.which, taskDone());
    });

    $(window).scroll(() => {
        if ($('.tutorial:hidden').length === 0) {
            const scroll = $(this).scrollTop(),
                nav = $('nav'),
                header = $('header'),
                pos = scroll + nav.height(),
                navOffset = header.offset().top + header.outerHeight();

            if (scroll > navOffset - navBarHeight) {
                nav.addClass('fixed_tutorial').next();
            } else {
                nav.removeClass('fixed_tutorial').next();
            }

            $('nav a').removeClass('active').each(function() {
                const target = $(this).attr('href'),
                    offset = $(target).offset(),
                    height = $(target).height();

                if (offset.top <= pos && pos < offset.top + height) {
                    $(this).addClass('active');
                    return false;
                }
            });
            redraw();
        }
    });

    $(window).resize(() => {
        if ($('.tutorial:hidden').length === 0) {
            redraw();
        }
    });

    $('.tutorial').show();

    ctx = document.getElementById("overlay").getContext("2d");
    drawNewFrame();
    setup();
};

$(document).ready(() => {
    if (typeof simpleStorage.get('visited') !== 'string') {
        $('.popup-background').show();
    }

    $('.startTutorial').click(() => {
        startTutorial();
    });
});

tutorialData.length =
    Object.keys(tutorialData).reduce(
            (acc, curr) => isNaN(curr) ? acc : acc + 1
    , 0);
