const valueEquals = (value) => (domObjects) => $(domObjects[0]).val() === value;

const notEmpty = (domObjects) => $(domObjects[0]).val() !== '';

const tutorialData = {
    defaultSettings: {
        textPosition: {x: 75, y: 40}
    },
    0: {
        textPosition: {x: 50, y: 50},
        headline: '{{tut head 0}}',
        explanation: '{{tut expl 0}}',
        task: '{{tut task 0}}'
    },
    1: {
        headline: '{{tut head 1}}',
        explanation: '{{tut expl 1}}',
        task: '{{tut task 1}}',
        highlightSelector: 'select[name=detaillevel]'
    },
    2: {
        headline: '{{tut head 2}}',
        explanation: `{{tut expl 2}}<label for="checkbox_experiments" style="pointer-events: auto; padding: 0; margin: 0;">,</label>
<ul>
${[
            ['{{trigger hodoscope information}}', '{{trigger hodoscope url}}'],
            ['{{cosmo information}}', '{{cosmo url}}'],
            ['{{polarstern information}}', '{{polarstern url}}'],
            ['{{neumayer information}}', '{{neumayer url}}'],
            ['{{zeuthen weather information}}', '{{zeuthen weather url}}']
        ].map(
          ([information, url]) => `<a target="_blank" href="${url}">${information}</a>`
        ).join('')}</ul>`,
        task: '{{tut task 2}}',
        highlightSelector: 'select[name=experiment0]',
        validator: valueEquals('Polarstern')
    },
    3: {
        headline: '{{tut head 3}}',
        explanation: '{{tut expl 3}}',
        task: '{{tut task 3}}',
        highlightSelector: 'select[name=s0]',
        validator: valueEquals('Polarstern/2017-2018_PS-nm-mt.h5:/raw/PS_mu_nm_data')
    },
    4: {
        headline: '{{tut head 4}}',
        explanation: `{{tut expl 4}}<ol>${
            [
                '{{1d histogram expl % <b>,</b>}}', 
                '{{xy diagram expl % <b>,</b>}}',
                '{{2d histogram expl % <b>,</b>}}',
                '{{profile expl % <b>,</b>}}',
                '{{map expl % <b>,</b>}}'
            ].map(v => `<li>${v}</li>`).join('')
            }</ol>`,
        task: '{{tut task 4}}',
        highlightSelector: 'select[name=m0]',
        validator: valueEquals('xy')
    },
    5: {
        headline: '{{tut head 5}}',
        explanation: '{{tut expl 5}}',
        task: '{{tut task 5}}',
        highlightSelector: 'select[name=x0]',
        validator: valueEquals('time')
    },
    6: {
        headline: '{{tut head 6}}',
        explanation: '{{tut expl 6}}',
        task: '{{tut task 6}}',
        highlightSelector: 'select[name=y0]',
        validator: valueEquals('mu_rate')
    },
    7: {
        headline: '{{tut head 7}}',
        explanation: '{{tut expl 7}}',
        task: '{{tut task 7}}',
        highlightSelector: 'input[name=t]',
        validator: notEmpty
    },
    8: {
        headline: '{{tut head 8}}',
        explanation: '{{tut expl 8}}',
        task: '{{tut task 8}}',
        highlightSelector: 'select[name=l]',
    },
    9: {
        headline: '{{tut head 9}}',
        explanation: '{{tut expl 9}}',
        task: '{{tut task 9}}',
        highlightSelector: 'button[type=submit]',
        doneOnClick: true
    },
    10: {
        headline: '{{tut head 10}}',
        explanation: '{{tut expl 10}} <a href=\'https://physik-begreifen-zeuthen.desy.de/e2198/e203474/e203596/e204023/index_ger.html#e222540\' target=\'blank_\'>,</a>',
        task: '{{tut task 10}}',
        highlightSelector: '#plotImage'
    },
    11: {
        headline: '{{tut head 11}}',
        explanation: '{{tut expl 11}}',
        task: '{{tut task 11}}',
        highlightSelector: '#downloadButtons'
    },
    12: {
        headline: '{{tut head 12}}',
        explanation: '{{tut expl 12}}',
        task: '{{tut task 12}}',
        highlightSelector: '#plotsettings,#loadsettings'
    },
    13: {
        headline: '{{tut head 13}}',
        explanation: '{{tut expl 13}}',
        task: '{{tut task 13}}',
        highlightSelector: '#session'
    },
    14: {
        headline: '{{tut head 14}}',
        explanation: '{{tut expl 14}}',
        task: '{{tut task 14}}',
        highlightSelector: '#savePlotButton',
        doneOnClick: true
    },
    15: {
        headline: '{{tut head 15}}',
        explanation: '{{tut expl 15}}',
        task: '{{tut task 15}}',
        highlightSelector: '.savedPlotImage',
        highlightDisabled: true
    },
    16: {
        headline: '{{tut head 16}}',
        explanation: '{{tut expl 16}}',
        task: '{{tut task 16}}',
        highlightSelector: '.btns',
        highlightDisabled: true
    },
    17: {
        textPosition: {x: 50, y: 50},
        headline: '{{tut head 17}}',
        explanation: '{{tut expl 17}}',
        task: '{{tut task 17}}'
    }
};
